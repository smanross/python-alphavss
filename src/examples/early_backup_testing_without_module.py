'''
    AlphaVSS based python module pre-beta testing version of a VSS Snapshot Set backup allowing
        for a persistent snapshot to be created

    **** Pylance/Pylint cant resolve CLR modules (expect errors suggesting these modules dont exist)
'''
import os
from os.path import exists
import sys
import clr


ARCH = 'x86'
if os.environ['PROCESSOR_ARCHITECTURE'] == 'AMD64':
    ARCH = 'x64'
# this is not ARM compatible

ALPHAVSS_BASE_PATH = os.path.expandvars(f'%ProgramFiles%\\AlphaVSS\\2.0.0\\net45\\{ARCH}')
if ALPHAVSS_BASE_PATH not in sys.path and exists(f'{ALPHAVSS_BASE_PATH}\\AlphaVSS.Common.DLL'):
    sys.path.append(ALPHAVSS_BASE_PATH)

try:
    clr.AddReference("AlphaVSS.Common") #pylint:disable=I1101
except Exception as ex:
    raise Exception('Error loading the AlphaVSS.Common Module - did you compile it, and install it in the suggested location') from ex

import Alphaleonis.Win32.Vss as alphavsslib #pylint:disable=E0401,C0413

# Get the default provider
provider = alphavsslib.VssFactoryProvider.Default

# Create a facotry
factory = provider.GetVssFactory()

# Build the BackupComponents object
cmp = factory.CreateVssBackupComponents()

# Tell the components we want to initialize it for Backup operations (as opposed to Restore Operations)
cmp.InitializeForBackup(None)

# SetContext with AppRollback enables Persistent ShadowCopies .Backup ( == 0) would be default and would release the ShadowCopies
# when this program closes (from an Exception or at the end of the script)
cmp.SetContext(alphavsslib.VssSnapshotContext.AppRollback) # Persistent

# list your volumes you want added to the shadowcopyset
volume_names = ['C:\\', 'D:\\', 'F:\\']

# Verify shadowcopies are supported on each volume
for volume_name in volume_names:
    if not cmp.IsVolumeSupported(volume_name):
        print(f'{volume_name} is not supported!!!!!')
        cmp.AbortBackup()
        cmp.Dispose()
        del cmp
        sys.exit(-1)
# If all our volumes are supported, gather writer metadata (required)
cmp.GatherWriterMetadata()

# Start a SnapshotSet (as opposed to an individual Snapshot)
set_id = cmp.StartSnapshotSet()

for volume_name in volume_names:
    # we validated the volumes above so just add them to the snapshotset and get the snapshot ID
    snap_id = cmp.AddToSnapshotSet(volume_name)
    print(f'snap_id ->> {snap_id} == {volume_name}')

#Set the backup state
cmp.SetBackupState(False, True, 1, False)

# Notify the writers to get ready for a snapshot operation
cmp.PrepareForBackup()

# Make the Shadow Copy Set from all the volume_names above
cmp.DoSnapshotSet()
