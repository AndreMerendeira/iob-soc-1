import os
import shutil

import iob_colors

import copy_srcs

import config_gen
import param_gen
import verilog_gen
import reg_gen
import io_gen
import doc_gen
import ipxact_gen

from iob_module import iob_module
from iob_instance import iob_instance


class iob_core(iob_module, iob_instance):
    """Generic class to describe how to generate a base IOb IP core"""

    def __init__(
        self,
        *args,
        is_top: bool = True,
        purpose: str = "hardware",
        topdir: str = ".",
        **kwargs,
    ):
        # Inherit attributes from superclasses
        super().__init__(*args, **kwargs)
        # CPU interface for control status registers
        self.set_default_attribute("csr_if", "iob")
        self.set_default_attribute("version", "1.0")
        self.set_default_attribute("previous_version", self.version)
        self.set_default_attribute("setup_dir", "")
        self.set_default_attribute("build_dir", "")
        # Overlap Read and Write register addresses
        self.set_default_attribute("rw_overlap", False)
        self.set_default_attribute("is_top_module", is_top)
        self.set_default_attribute("use_netlist", False)
        self.set_default_attribute("is_system", False)
        # List of FPGAs supported by this core
        self.set_default_attribute("board_list", [])
        # Where to copy sources of this core
        self.set_default_attribute("purpose", purpose)

        # Read-only dictionary with relation between the 'purpose' and
        # the corresponding source folder
        self.PURPOSE_DIRS: dict = {
            "hardware": "hardware/src",
            "simulation": "hardware/simulation/src",
            "fpga": "hardware/fpga/src",
        }

        if is_top:
            self.build_dir = f"../{self.name}_{self.version}/build"
            topdir = self.build_dir
        else:
            self.build_dir = topdir
        self.setup_dir = find_module_setup_dir(self, os.getcwd())

        if is_top:
            self.__create_build_dir()

        # Copy files from LIB to setup various flows
        # (should run before copy of files from module's setup dir)
        if is_top:
            copy_srcs.flows_setup(self)

        # Copy files from the module's setup dir
        copy_srcs.copy_rename_setup_directory(self)

        # Generate config_build.mk
        config_gen.config_build_mk(self)

        # Generate configuration files
        config_gen.generate_confs(self)

        # Generate parameters
        param_gen.generate_params(self)

        # Generate ios
        io_gen.generate_ports(self)

        # Generate wires
        # TODO: wire_gen.generate_wires(self)

        # Generate csr interface
        csr_gen_obj, reg_table = reg_gen.generate_csr(self)

        # Generate instances
        # TODO: block_gen.generate_blocks(self)

        # Generate snippets
        # TODO: snippet_gen.generate_snippets(self)

        # TODO: Generate a global list of signals
        # This list is useful for a python based simulator
        # 1) Each input of the top generates a global signal
        # 2) Each output of a leaf generates a global signal
        # 3) Each output of a snippet generates a global signal
        #    A snippet is a piece of verilog code manually written (should also receive a list of outputs by the user).
        #    A snippet can also be any method that generates a new signal, like the `concat_bits`, or any other that performs logic in from other signals into a new one.
        # TODO as well: Each module has a local `snippets` list.

        if is_top:
            # Replace Verilog snippet includes
            self._replace_snippet_includes()
            # Clean duplicate sources in `hardware/src` and its subfolders (like `hardware/simulation/src`)
            self._remove_duplicate_sources()
            # Generate docs
            doc_gen.generate_docs(self, csr_gen_obj, reg_table)
            # Generate ipxact file
            # if self.generate_ipxact: #TODO: When should this be generated?
            #    ipxact_gen.generate_ipxact_xml(self, reg_table, self.build_dir + "/ipxact")

    def __create_build_dir(self):
        """Create build directory. Must be called from the top module."""
        assert (
            self.is_top_module
        ), f"{iob_colors.FAIL}Module {self.name} is not a top module!{iob_colors.ENDC}"
        os.makedirs(self.build_dir, exist_ok=True)
        # Create hardware directories
        os.makedirs(f"{self.build_dir}/hardware/src", exist_ok=True)
        os.makedirs(f"{self.build_dir}/hardware/simulation/src", exist_ok=True)
        os.makedirs(f"{self.build_dir}/hardware/fpga/src", exist_ok=True)

        os.makedirs(f"{self.build_dir}/doc", exist_ok=True)
        os.makedirs(f"{self.build_dir}/doc/tsrc", exist_ok=True)

        shutil.copyfile(
            f"{copy_srcs.get_lib_dir()}/build.mk", f"{self.build_dir}/Makefile"
        )

    def clean_build_dir(self):
        """Clean build directory. Must be called from the top module."""
        self.build_dir = f"../{self.name}_{self.version}"
        print(
            f"{iob_colors.ENDC}Cleaning build directory: {self.build_dir}{iob_colors.ENDC}"
        )
        # if build_dir exists run make clean in it
        if os.path.exists(self.build_dir):
            os.system(f"make -C {self.build_dir} clean")
        shutil.rmtree(self.build_dir, ignore_errors=True)

    def print_build_dir(self):
        """Print build directory."""
        self.build_dir = f"../{self.name}_{self.version}"
        print(self.build_dir)

    def _remove_duplicate_sources(self):
        """Remove sources in the build directory from subfolders that exist in `hardware/src`"""
        # Go through all subfolders defined in PURPOSE_DIRS
        for subfolder in self.PURPOSE_DIRS.values():
            # Skip hardware folder
            if subfolder == "hardware/src":
                continue

            # Get common srcs between `hardware/src` and current subfolder
            common_srcs = find_common_deep(
                os.path.join(self.build_dir, "hardware/src"),
                os.path.join(self.build_dir, subfolder),
            )
            # Remove common sources
            for src in common_srcs:
                os.remove(os.path.join(self.build_dir, subfolder, src))
                # print(f'{iob_colors.INFO}Removed duplicate source: {os.path.join(subfolder, src)}{iob_colors.ENDC}')

    def _replace_snippet_includes(self):
        verilog_gen.replace_includes(
            self.setup_dir, self.build_dir, self.ignore_snippets
        )


def find_common_deep(path1, path2):
    """Find common files (recursively) inside two given directories
    Taken from: https://stackoverflow.com/a/51625515
    :param str path1: Directory path 1
    :param str path2: Directory path 2
    """
    return set.intersection(
        *(
            set(
                os.path.relpath(os.path.join(root, file), path)
                for root, _, files in os.walk(path)
                for file in files
            )
            for path in (path1, path2)
        )
    )


def find_module_setup_dir(core, search_path):
    """Searches for a core's setup directory, and updates `core.setup_dir` attribute.
    param core: The core object
    param search_path: The directory to search
    """
    # Use os.walk() to traverse the directory tree
    for root, directories, files in os.walk(search_path):
        for file in files:
            # Check if file name matches '<core_class_name>.py'
            if file.split(".")[0] == core.__class__.__name__:
                # print(os.path.join(root, file)) # DEBUG
                return root

    raise Exception(
        f"{iob_colors.FAIL}Setup dir of {core.name} not found in {search_path}!{iob_colors.ENDC}"
    )


def find_dict_in_list(list_obj, name):
    """Find an dictionary with a given name in a list of dictionaries"""
    for i in list_obj:
        if i["name"] == name:
            return i
    raise Exception(
        f"{iob_colors.FAIL}Could not find element with name: {name}{iob_colors.ENDC}"
    )
