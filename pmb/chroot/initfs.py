"""
Copyright 2017 Oliver Smith

This file is part of pmbootstrap.

pmbootstrap is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

pmbootstrap is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with pmbootstrap.  If not, see <http://www.gnu.org/licenses/>.
"""
import os
import logging
import pmb.chroot.initfs_hooks
import pmb.chroot.other
import pmb.chroot.apk
import pmb.helpers.cli


def build(args, flavor, suffix):
    logging.info("(" + suffix + ") mkinitfs " + flavor)
    release_file = (args.work + "/chroot_" + suffix + "/usr/share/kernel/" +
                    flavor + "/kernel.release")
    with open(release_file, "r") as handle:
        release = handle.read().rstrip()
    pmb.chroot.root(args, ["mkinitfs", "-o", "/boot/initramfs-" + flavor, release],
                    suffix)


def extract(args, flavor, suffix, log_message=False):
    """
    Extract the initramfs to /tmp/initfs-extracted and return the outside
    extraction path.
    """
    # Extraction folder
    inside = "/tmp/initfs-extracted"
    outside = args.work + "/chroot_" + suffix + inside
    if os.path.exists(outside):
        if pmb.helpers.cli.ask(args, "Extraction folder " + outside +
                               " already exists. Do you want to overwrite it?") != "y":
            raise RuntimeError("Aborted!")
        pmb.chroot.root(args, ["rm", "-r", inside], suffix)

    # Extraction script (because passing a file to stdin is not allowed
    # in pmbootstrap's chroot/shell functions for security reasons)
    with open(args.work + "/chroot_" + suffix + "/tmp/_extract.sh", "w") as handle:
        handle.write(
            "#!/bin/sh\n"
            "cd " + inside + " && cpio -i < _initfs\n")

    # Extract
    commands = [["mkdir", "-p", inside],
                ["cp", "/boot/initramfs-" + flavor, inside + "/_initfs.gz"],
                ["gzip", "-d", inside + "/_initfs.gz"],
                ["cat", "/tmp/_extract.sh"],  # for the log
                ["sh", "/tmp/_extract.sh"],
                ["rm", "/tmp/_extract.sh", inside + "/_initfs"]
                ]
    for command in commands:
        pmb.chroot.root(args, command, suffix)

    # Return outside path for logging
    return outside


def ls(args, flavor, suffix):
    tmp = "/tmp/initfs-extracted"
    extract(args, flavor, suffix)
    pmb.chroot.user(args, ["ls", "-lahR", "."], suffix, tmp, log=False)
    pmb.chroot.root(args, ["rm", "-r", tmp], suffix)


def frontend(args):
    # Find the appropriate kernel flavor
    suffix = "rootfs_" + args.device
    flavor = pmb.chroot.other.kernel_flavor_autodetect(args, suffix)
    if hasattr(args, "flavor") and args.flavor:
        flavor = args.flavor

    # Handle initfs actions
    action = args.action_initfs
    if action == "build":
        build(args, flavor, suffix)
    elif action == "extract":
        dir = extract(args, flavor, suffix)
        logging.info("Successfully extracted to: " + dir)
    elif action == "ls":
        ls(args, flavor, suffix)

    # Handle hook actions
    elif action == "hook_ls":
        pmb.chroot.initfs_hooks.ls(args, suffix)
    else:
        if action == "hook_add":
            pmb.chroot.initfs_hooks.add(args, args.hook, suffix)
        elif action == "hook_del":
            pmb.chroot.initfs_hooks.delete(args, args.hook, suffix)

        # Rebuild the initfs for all kernels after adding/removing a hook
        for flavor in pmb.chroot.other.kernel_flavors_installed(args, suffix):
            build(args, flavor, suffix)