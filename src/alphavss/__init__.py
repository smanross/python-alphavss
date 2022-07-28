'''
    author: steven@manross.net
    description: Enable the use of VSSProvider, VSSSnapshot & VSSSnapshotSet in Python via C DLL functions in AlphaVSS
    version: 0.0.1.1

    alphavss API reference: https://alphavss.alphaleonis.com/api/Alphaleonis.Win32.Vss.VssFactoryProvider.html
    alphavss GIT source code:  https://github.com/alphaleonis/AlphaVSS/
    alphavss GIT Samples source code:  https://github.com/alphaleonis/AlphaVSS-Samples

    This module is all centered around making Shadow Copies of drives in Windows Systems for the purpose of backing up files at a point in time.
'''
import sysconfig
import os
from os.path import exists
import sys

ARCH = 'x86'
if os.environ['PROCESSOR_ARCHITECTURE'] == 'AMD64':
    ARCH = 'x64'
if os.environ['PROCESSOR_ARCHITECTURE'] == 'ARM64':
    raise Exception("Error Loading python module: this isn't currently known to work for ARM64 environments")

# All the DLLs for AlphaVSS should be located in the ARCH dir for your system: AlphaVSS.Common.dll, AlphaVSS.x64.dll (or ALphaVSS.x86.dll)
ALPHAVSS_BASE_PATH = f"{sysconfig.get_paths()['purelib']}/alphavss/lib/ALphaVSS/2.0.0/net45/{ARCH}"
if ALPHAVSS_BASE_PATH not in sys.path and exists(f'{ALPHAVSS_BASE_PATH}\\AlphaVSS.Common.DLL'):
    sys.path.append(ALPHAVSS_BASE_PATH)
    # you could have the DLLs somewhere else and already include that PATH in your system PATH

from alphavss.models import VSSProvider, VSSSnapshotSet, VSSSnapshot
