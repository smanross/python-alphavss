'''
    Sample/Test of getting the VSSProvider and querying snapshots/snapshotsets and trying to expose/unexpose the snapshots as local drive letters and paths.

    Requires:
     * AlphaVSS compiled .NET Framework DLLs (free source code, they just need to be compiled with Visual Studio and .NET Framework 4.5)
            https://github.com/alphaleonis/AlphaVSS/
     * python pip package: pythonnet (import clr)
     * My Python Classes (alphavss)
'''

import os
from os.path import exists
import time
from alphavss.models import VSSProvider, ExposedRemotely, AppRollback
import Alphaleonis.Win32.Vss as alphavsslib #pylint:disable=E0401,C0413


sleep_time = 15 # 15 seconds

# Avoid the "lower" letters of the alphabet as they are commonly used
# We could add A and B as floppy drives are all but gone and USB drives typically never try to use those
snap_letters = 'MNOPQRSTUVWXYZ'
snap_drive_letters = [letter + ':\\' for letter in snap_letters]
context = AppRollback

provider = VSSProvider(operation='query', context=context, debug=True)
snap_set_list = provider.query_snapshots()
print()
if not snap_set_list:
    print('You dont have any snapshots saved on this computer')
else:
    snapshot_expose_root = 'c:\\temp\\snapshots'
    if not exists(snapshot_expose_root):
        os.makedirs(snapshot_expose_root)
    x = 0
    for snap_set in snap_set_list:
        if snap_set.set_id:
            print(f'set: {snap_set.set_id}')
            print('    exposing as drive letters!!!')
            for snap in snap_set.snapshots:
                print(f'\tset id: {snap.set_id} -- snap_id: {snap.snap_id}')
                while exists(snap_drive_letters[x]):
                    x += 1
                    if x > len(snap_letters):
                        raise Exception('There are no more drive letters available to expose a snapshot set to (they are all used???)')

                # Expose to a drive letter
                snap.expose_snapshot(snap_drive_letters[x])
                x += 1

            print('    waiting a bit so you can see the changes in Windows Explorer')
            time.sleep(sleep_time)
            print('    exposing as paths to an existing drive!!!')
            for snap in snap_set.snapshots:
                # P.S. You can't expose a single snapshot multiple places, so we unexpose it before we expose it again somewhere else
                snap.unexpose_snapshot()

                # expose to an existing path on a drive
                # if this path is an empty folder # 'c:\\temp\\snapshot\\c', expose the snapshot here
                if not exists(f'{snapshot_expose_root}\\{snap.volume_name[:1].lower()}'):
                    os.makedirs(f'{snapshot_expose_root}\\{snap.volume_name[:1].lower()}')
                snap.expose_snapshot(f'{snapshot_expose_root}\\{snap.volume_name[:1].lower()}')

            print('    waiting a bit so you can see the changes in Windows Explorer')
            time.sleep(sleep_time)
            for snap in snap_set.snapshots:
                # P.S. You can't expose a single snapshot multiple places, so we unexpose it before we expose it again somewhere else
                snap.unexpose_snapshot()
            print()
            # Note, you can also expose as a windows share as well although that's not exampled here and you's have to change the default ExposeLocally to ExposeRemotely
            print('    exposing as paths to a windows share!!!')
            for snap in snap_set.snapshots:
                # expose and unexpose to awindows share
                snap.expose_snapshot(f'snapshot-{snap.volume_name[:1].lower()}$', attributes=ExposedRemotely)

            print('    waiting a bit so you can see the changes in "Computer Management-> Shared Folders -> Shares"')
            time.sleep(sleep_time)
            for snap in snap_set.snapshots:
                # P.S. You can't expose a single snapshot multiple places, so we unexpose it before we expose it again somewhere else
                snap.unexpose_snapshot()

            # Theoretically, you could mount a snapshot to a directory 261+ characters deep with this notation on the expose_path
            # (Invoking the LFN API using "\\\\?\\" prefix on the directory name (Not tested yet)
            # if this directory below existed already
            # for snap in snap_set.snapshots:
            #     snap.expose_snapshot('\\\\?\\c:\\temp\\some-super-long---deep-path--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------snapshot\\c')
            #     snap.unexpose_snapshot()
