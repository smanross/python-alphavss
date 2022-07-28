'''
    author: steven@manross.net
    description: Enable the use of VSSProvider, VSSSnapshot & VSSSnapshotSet in Python via C DLL functions in AlphaVSS
    version: 0.0.1.1

    alphavss API reference: https://alphavss.alphaleonis.com/api/Alphaleonis.Win32.Vss.VssFactoryProvider.html
    alphavss GIT source code:  https://github.com/alphaleonis/AlphaVSS/
    alphavss GIT Samples source code:  https://github.com/alphaleonis/AlphaVSS-Samples

    This module is all centered around making Shadow Copies of drives in Windows Systems for the purpose of backing up files at a point in time.
'''
import os
from os.path import exists
import sys
from alphavss.models import VSSProvider, VSSSnapshotSet, VSSSnapshot

ARCH = 'x86'
if os.environ['PROCESSOR_ARCHITECTURE'] == 'AMD64':
    ARCH = 'x64'
if os.environ['PROCESSOR_ARCHITECTURE'] == 'ARM64':
    raise Exception("Error Loading python module: this isn't currently known to work for ARM64 environments")

# change it if you want it somewhere else or make that directory part of your PATH
# All the DLLs for AlphaVSS should be located in the ARCH dir for your system: AlphaVSS.Common.dll, AlphaVSS.x64.dll (or ALphaVSS.x86.dll)
ALPHAVSS_BASE_PATH = os.path.expandvars(f"%ProgramFiles%\\AlphaVSS\\2.0.0\\net45\\{ARCH}")
if ALPHAVSS_BASE_PATH not in sys.path and exists(f'{ALPHAVSS_BASE_PATH}\\AlphaVSS.Common.DLL'):
    sys.path.append(ALPHAVSS_BASE_PATH)
    # you could have the DLLs somewhere else and already include that PATH in your system PATH

# SnapshotAttributes
# https://github.com/alphaleonis/AlphaVSS/blob/13462e657f7993da5c80f835d219bbe82079ce75/src/AlphaVSS.Common/Enumerations/VssVolumeSnapshotAttributes.cs
Backup = 0x0 # 0
Persistent = 0x00000001 # 1
NoAutoRecovery = 0x00000002 # 2
ClientAccessible = 0x00000004 # 4
NoAutoRelease = 0x00000008 # 8
NoWriters = 0x00000010 # 16
Transportable = 0x00000020 # 32
NotSurfaced = 0x00000040 # 64
NotTransacted = 0x00000080 # 128
HardwareAssisted = 0x00010000 # 65536
Differential = 0x00020000 # 131072
Plex = 0x00040000 # 262144
Imported = 0x00080000 # 524288
ExposedLocally = 0x00100000 # 1048576
# ExposedLocally = alphavsslib.VssVolumeSnapshotAttributes.ExposedLocally
ExposedRemotely = 0x00200000 # 2097152
# ExposedRemotely = alphavsslib.VssVolumeSnapshotAttributes.ExposedRemotely
AutoRecover = 0x00400000 # 4194304
RollbackRecovery = 0x00800000 # 8388608
DelayedPostSnapshot = 0x01000000 # 16777216
TxFRecovery = 0x02000000 # 33554432
APpRollback = Persistent | NoAutoRelease
# This one I am testing in place of "All" from https://github.com/alphaleonis/AlphaVSS/blob/13462e657f7993da5c80f835d219bbe82079ce75/src/AlphaVSS.Common/Enumerations/VssSnapshotContext.cs
# due to INT conversion issue
All = TxFRecovery | DelayedPostSnapshot | RollbackRecovery | AutoRecover | ExposedRemotely | ExposedLocally | Imported | Plex | Differential | HardwareAssisted | NotTransacted | NotSurfaced | Transportable | NoWriters | NoAutoRelease | ClientAccessible | NoAutoRecovery | Persistent | Backup # 67043583

snapshot_attr_names = {ExposedLocally: 'Locally',
                       ExposedRemotely: 'Remotely'
}
