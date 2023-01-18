import argparse
import os
import datetime
import shutil
import subprocess
import tarfile
import yaml
import importlib
import tempfile
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from Delta import DeltaEmbedded
from Delta import LoadableModules


bacnet = DeltaEmbedded.BACnetInterface()

META_DATA_FILES = {
        "name": ".MODULE_NAME",
        "time": ".MODIFIED_TIME",
}

def set_module_name(fil_instance, module_name):
    """Save name in module's installer directory."""
    module_name_file_path = Path(
            LoadableModules.INSTALLER_DIR,
            f"FIL{fil_instance}",
            META_DATA_FILES["name"],
    )
    with open(module_name_file_path, "w") as name_file:
        name_file.write(module_name)

def get_module_name(fil_instance):
    """Read saved name for a module."""
    module_name_file_path = Path(
            LoadableModules.INSTALLER_DIR,
            f"FIL{fil_instance}",
            META_DATA_FILES["name"],
    )
    if module_name_file_path.is_file():
        with open(module_name_file_path, "r") as name_file:
            return name_file.read()
    else:
        return ""

def get_fil_instance(module_name):
    """Read saved FIL object instance for a module."""
    for module_name_file_path in Path(LoadableModules.INSTALLER_DIR).glob("*/.MODULE_NAME"):
        with open(module_name_file_path, "r") as name_file:
            name_from_file = name_file.read()
            if name_from_file == module_name:
                fil_object_id = module_name_file_path.parent.name
                return int(fil_object_id.strip("FIL"))
    else:
        # module was not found
        return -1

def get_fil_instance_from_data_path(fil_data_path):
    """Extract FIL object instance from path to .dat file."""
    data_filename = Path(fil_data_path).name
    return int(data_filename.strip("FIL.dat"))

def set_fil_modified_time(fil_instance, data_path):
    """Save timestamp in installer dir for a module."""
    fil_modified_time_path = Path(
            LoadableModules.INSTALLER_DIR,
            f"FIL{fil_instance}",
            META_DATA_FILES["time"],
    )
    with open(fil_modified_time_path, "w") as time_file:
        modified_time = Path(data_path).stat().st_mtime
        time_file.write(str(modified_time))

def fil_is_current(fil_data_path):
    """Check if FIL data has changed since it was installed."""
    fil_instance = get_fil_instance_from_data_path(fil_data_path)
    current_modified_time = str(Path(fil_data_path).stat().st_mtime)

    modified_time_file_path = Path(
            LoadableModules.INSTALLER_DIR,
            f"FIL{fil_instance}",
            META_DATA_FILES["time"],
    )
    if modified_time_file_path.is_file():
        with open(modified_time_file_path, "r") as time_file:
            saved_modified_time = time_file.read()
        return (saved_modified_time == current_modified_time)
    else:
        # modified time was not saved, fil is not installed
        return False

def install_package(installer_subdir, package_info, action="install"):
    """Find and run install handler for a package (ie. single item in the manifest)."""
    for installer_info in package_info["installers"]:
        # get extension from filename
        installer_file_name = installer_info["file_name"]

        installer_full_path = os.path.join(
                LoadableModules.INSTALLER_DIR,
                installer_subdir,
                installer_file_name,
        )
        installer_ext = Path(installer_file_name).suffix.strip(".")
        
        # try to import
        try:
            module_name = f"installer_modules.install_{installer_ext}"
            installer_module = importlib.import_module(module_name)
        except ModuleNotFoundError as e:
            continue
        # found an installer that we have a handler for
        break
    else:
        # did not find an installer that we can use
        return False, f"No install handler found for {package_info['name']}"
    
    if action == "install":
        return installer_module.install(installer_full_path)
    elif action == "uninstall":
        return installer_module.uninstall(installer_full_path)


def decrypt_module(encrypted_file_path, decrypted_file_path):
    """
    Decrypt a loadable module.
    Encrypted data is expected to consist of:
       - 256 bytes Fernet key that was encrypted with an RSA public key
       - tarball encrypted with the Fernet key
    Decrypting is done in two steps.  We use the RSA private key to decrypt the Fernet key, which
    is then used to decrypt the tarball.
    """
    # TODO: where should the certificate be stored?
    # load private key
    private_key_file_path = Path("/usr/delta/python_interfaces/private.pem")
    with open(private_key_file_path, "rb") as private_key_file:
        private_key = serialization.load_pem_private_key(
                private_key_file.read(),
                password=None,
                backend=default_backend(),
        )
   
    # decrypt data key
    with open(encrypted_file_path, "rb") as encrypted_module:
        encrypted_data_key = encrypted_module.read(256)
        data_key = private_key.decrypt(
                encrypted_data_key,
                padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None,
                )
        )

        # use data key to decrypt data 
        with open(decrypted_file_path, "wb") as decrypted_module:
            decrypted_module.write(
                    Fernet(data_key).decrypt(
                            encrypted_module.read(),
                    )
            )


def install_fil(fil_data_path):
    """
    Extract and install FIL data.

    Arguments:
        fil_data_path -- Location of FIL data.  Expected format is an encrypted tarball 
            containing a manifest and one or more packages to install.
    """
    fil_instance = get_fil_instance_from_data_path(fil_data_path)
    object_id = f"FIL{fil_instance}"
    file_name = bacnet.read_value(f"{object_id}.object_name")
    
    logger = LoadableModules.Logger(fil_instance=fil_instance)
    logger.clear()
    logger.log_status(f"Begin install of {object_id}: {file_name}")

    installer_dir = Path(LoadableModules.INSTALLER_DIR, object_id)
    installer_dir.mkdir(parents=True, exist_ok=True)
    
    # record time fil was modified to compare to when looking for new changes 
    set_fil_modified_time(fil_instance, fil_data_path)

    with tempfile.TemporaryDirectory() as decrypt_dir:
        encrypted_data_path = Path(decrypt_dir, "encrypted.tar.gz")
        decrypted_data_path = Path(decrypt_dir, "decrypted.tar.gz")
        shutil.copy2(fil_data_path, encrypted_data_path)

        try:
            decrypt_module(encrypted_data_path, decrypted_data_path)
        except ValueError as e:
            logger.log_status("Error: failed to decrypt.")
            return False

        try:
            tar = tarfile.open(decrypted_data_path)
            with tar.extractfile("manifest.yaml") as manifest_file:
                manifest = yaml.safe_load(manifest_file)
                module_name = manifest["name"]
            
            tar.extractall(path=installer_dir)
        except (tarfile.ReadError, KeyError, FileNotFoundError) as e:
            # does not contain manifest or manifest is wrong format
            logger.log_status("Error: unexpected FIL data format")
            return False

    logger.log_status(f"Processing manifest {manifest['name']}")

    if len(manifest["items"]) == 0:
        logger.log_status("Nothing to do: no items found in manifest")
        return False

    for payload_item in manifest["items"]:
        install_success, message = install_package(object_id, payload_item, action="install")
        logger.log_status(message)
        if not install_success:
            # run uninstaller to cleanup in case module is partially installed
            uninstall_module(fil_instance, clean_metadata=False, clean_data_dir=False)
            break
    else:
        # all packages installed successfully
        logger.log_status("All packages successfully installed!")

        # register module data for backup
        bacnet.server.registerdirectoryforbackup(
                bacnet.user_key,
                str(LoadableModules.get_module_data_dir(module_name=module_name)),
                True,
        )

    # create mapping back to BACnet FIL object
    set_module_name(fil_instance, module_name)

    return install_success 

    
def uninstall_module(fil_instance, clean_metadata=True, clean_data_dir=True):
    """
    Remove all packages listed in a previously installed FIL's install manifest.

    Arguments:
        fil_instance -- BACnet FIL object instance
        clean_metadata -- also delete .MODIFIED_TIME and .MODULE_NAME.  Specify False if this
            uninstall is due to a failed install so that modified time can be checked to prevent
            repeatedly re-attempting the install.
        clean_data_dir -- also delete this module's data directory.  Specify False if this
            uninstall is part of an upgrade or due to an install failure.
    """
    module_name = get_module_name(fil_instance)
    installer_dir = Path(LoadableModules.INSTALLER_DIR) / f"FIL{fil_instance}" 

    if clean_data_dir:
        # unregister module data for backup and remove it
        bacnet.server.unregisterdirectoryfrombackup(
                bacnet.user_key,
                str(LoadableModules.get_module_data_dir(module_name=module_name)),
        )
        LoadableModules.clear_module_data_dir(module_name=module_name)

    # load manifest
    manifest_path = installer_dir / "manifest.yaml"
    if manifest_path.exists():
        with manifest_path.open() as manifest_file:
            manifest = yaml.safe_load(manifest_file)

        print(f"Processing manifest {manifest['name']}")
        item_list = reversed(manifest["items"])
        for payload_item in item_list:
            install_package(module_name, payload_item, action="uninstall")

    # remove installer files
    for f in installer_dir.glob("*"):
        if clean_metadata or f.name not in META_DATA_FILES.values():
            f.unlink()
    # remove directory if it is now empty
    if len(list(installer_dir.iterdir())) == 0:
        installer_dir.rmdir()

    return True


def uninstall_fil(fil_data_path):
    """Remove a module previously installed from FIL data."""
    fil_instance = get_fil_instance_from_data_path(fil_data_path)
    module_name = get_module_name(fil_instance)
    if not module_name:
        print(f"Nothing to do - FIL{fil_instance} is not installed!")
        return True

    return uninstall_module(fil_instance)


def find_changed_modules():
    """Find modules whose FIL object data has been removed, modified, or added."""
    modules = {
        "added": [],
        "modified": [],
        "removed": [],
    }

    # find modules that do not have FIL data
    for install_subdir in Path(LoadableModules.INSTALLER_DIR).glob("*/"):
        # get fil object id from path
        fil_object_id = install_subdir.name
        instance = int(fil_object_id.strip("FIL"))
        # check if object still exists
        if (bacnet.find_object_by_id(fil_object_id) is None
                or not bacnet.read_value(f"{fil_object_id}.object_name").endswith(".dlm")):
            modules["removed"].append(instance)

    # find modules that have changed or are newly added
    for fil_data_path in Path(LoadableModules.FIL_DATA_DIR).glob("FIL*.dat"):
        instance = get_fil_instance_from_data_path(fil_data_path)
        object_name = bacnet.find_object_by_id(f"fil{instance}")
        if (object_name is not None
                and object_name.endswith(".dlm")
                and not fil_is_current(fil_data_path)):
            
            module_name = get_module_name(instance)
            if module_name == "":
                # not found in installer directory
                modules["added"].append(instance)
            else:
                # a previous version already installed
                modules["modified"].append(instance)

    return modules

def sync_with_bacnet_db(changed_modules=None):
    """Install/uninstall based on changes to FIL object data."""

    if changed_modules is None:
        changed_modules = find_changed_modules()
  
    for instance in changed_modules["removed"]:
        uninstall_module(instance)

    for instance in changed_modules["modified"]:
        uninstall_module(instance, clean_data_dir=False)

    for instance in changed_modules["added"] + changed_modules["modified"]:
        install_fil(Path(LoadableModules.FIL_DATA_DIR, f"FIL{instance}.dat"))
        

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Install dlm from fil data.")
    install_mode = parser.add_mutually_exclusive_group(required=True)
    install_mode.add_argument("--install", action="store_true", default=False, help="Install the module.")
    install_mode.add_argument("--uninstall", action="store_true", default=False, help="Uninstall the module.")
    install_mode.add_argument("--sync", action="store_true", default=False, help="Sync modules with bacnet FIL objects.")
    parser.add_argument("--data_path", type=str, help="FIL object data file to install. Required for --install or --uninstall")

    args = parser.parse_args()
    
    if args.install:
        if args.data is None:
            parser.print_usage()
            exit(1)
        result = install_fil(args.data)
    elif args.uninstall:
        if args.instance is None:
            parser.print_usage()
            exit(1)
        result = uninstall_fil(args.data)
    elif args.sync:
        result = sync_with_bacnet_db()
    
    exit(0 if result else 1)


