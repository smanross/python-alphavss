'''
    This module requires AlphaVSS:   You need to compile it for your system using Visual Studio 2019 or newer
        and place the DLLs in some directory (that the system PATH will find, or use my suggestion below for ALPHAVSS_BASE_PATH)
        https://github.com/alphaleonis/AlphaVSS

        Sorry..  My python-fu isnt amazing enough to build the DLLs for you in a setup script!  :(

    My testing is with Server 2016 (and eventually in Server 2019, 2022)
      * All older Server OSes should work through 2003 (providing you can install the .NET Framework 4.5) but will likely go untested
        since these OSes are basically deprecated/unsupported/"security risks"

    Prerequisites:
      * the applicable .NET Framework 4.5 or newer for your OS
      * .NET Core 3.1 or newer (if you plan to build the netcore DLLs -- I did not need them, but downloaded it anyway)
      * python module pythonnet (tested with Python 3.9/pythonnet v2.5.2, newer builds likely should work)

    Notes:
        * AlphaVSS is FREE at the time of this writing
        * DO NOT install via NuGet/Powershell and try to take the powershellmodule files as your AlphaVSS.platform.dll files
        * Building the DLLs from source was a much better way of getting the files and worked perfectly on version 2.0.0.
        * This module was built by looking at and copying the logic from the AlphaVSS Samples (Specifically VSSBackup/VSSBackup.cs):
            https://github.com/alphaleonis/AlphaVSS-Samples/tree/develop/src

    Version:
        20220711 - basic framework built, initial testing and python classes work
        20220722 - changes to structure of classes, worked more on streamlining code
                   add expose_snapshot function
        20220727 - worked through bugs, and functionality issues in building the examples (expose/unexpose locally/remotely)
'''
from os.path import exists
import wmi
import clr
import System #pylint:disable=E0401
# Python .NET moduels will always show as reportMissingImports from Pylance or E0401 from Pylint
from System import Guid #pylint:disable=E0401
from alphavss import ExposedLocally, ExposedRemotely, Backup, snapshot_attr_names

try:
    clr.AddReference("AlphaVSS.Common") #pylint:disable=I1101
except Exception as ex:
    raise Exception('Error loading the AlphaVSS.Common Module') from ex

import Alphaleonis.Win32.Vss as alphavsslib #pylint:disable=E0401,C0413


class VSSProvider(object):
    '''
        AlphaVSS .NET Framework 4.5 Provider
    '''
    def __init__(self, operation='backup', context=Backup, debug=False):
        self.debug = debug
        self.operation = operation
        self.context = context
        self.initialized_for = None
        try:
            self._object = alphavsslib.VssFactoryProvider.Default
        except Exception as e:
            raise Exception('Error getting the VssFactoryProvider') from e

        try:
            self.factory = self._object.GetVssFactory()
        except System.BadImageFormatException as e:
            # Got this before I started compiling my own DLL from Visual Studio
            raise Exception('Bad Image Format') from e
        except OSError as e:
            raise Exception('Error getting the VssFactory (are you using the correct AlphaVSS binaries)') from e
            # FileNotFound likely suggests you are missing a file or have a missing dependency
            #  While dependencyWalker suggests that some API*.dll files are missing, they likely
            #      are false positives since those libraries got moved to other places in the Windows API
            # My issues initially here were because I pulled the libraries from the Powershell modules dir, instead
            #    of building them from scratch with VS 2019

    def _initialize(self, components):
        if self.operation in ['backup', 'query']:
            self.initialize_for_backup(components)

        if self.operation == 'restore':
            self.initialize_for_restore(components)

        return True

    def initialize_for_backup(self, components):
        '''
            Prepare for Backup, Query or Expose
        '''
        if self.operation in ['backup', 'query']:
            components.InitializeForBackup(None)
            self.initialized_for = self.operation

        components.SetContext(self.context)
        if self.operation == 'backup':
            components.GatherWriterMetadata()
        # cant do this here because we need the snapshot objects for it
        # or store them somewhere/return the variable
        # if self.operation == 'query':
        #     snapshots = components.QuerySnapshots()
        return True

    def initialize_for_restore(self, components):
        '''
            Prepare for Restore
        '''
        components.InitializeForRestore(None)
        # components.GatherWriterMetadata()
        self.initialized_for = self.operation
        return True

    def create_backup_components(self):
        '''
            This object can only be used for a single Backup, Restore, or Query Operation
        '''
        try:
            cmp = self.factory.CreateVssBackupComponents()

        except Exception as e:
            raise Exception('Error creating the VSSBackupComponents object') from e

        return cmp

    def query_snapshots(self):
        '''
            Query the existing Snapshots on the system

            context:
                https://github.com/alphaleonis/AlphaVSS/blob/13462e657f7993da5c80f835d219bbe82079ce75/src/AlphaVSS.Common/Enumerations/VssSnapshotContext.cs

                *** context can be a combination of the VssSnapshotContext options and VssVolumeSnapshotArrtibutes options ORed together
                alphavss.VssSnapshotContext.Backup = 0
                alphavss.VssSnapshotContext.All = 4294967295  # Doesn't work because of an INT conversion issue in .NET and/or pythonnet
                    # Seems related: https://github.com/pythonnet/pythonnet/issues/950
                .ClientAccessibleWriters = 13
                .ClientAccessible = 29
                .AppRollback = 9 (Persistent (1) + NoAutoRelease(8))
                .NasRollback = 25 (NoWriters/FileShareBackup + Persistent + NoAutoRelease)
                .FileShareBackup = 16 (= .NoWriters)

                alphavsslib.VssVolumeSnapshotAttributes.Persistent = 1
                alphavsslib.VssVolumeSnapshotAttributes.NoAutoRelease = 8
                alphavsslib.VssSnapshotContext.AppRollback = 9 (Persistent, NoAutoRelease)
        '''
        cmp = self.create_backup_components()
        self._initialize(cmp)
        snaps = cmp.QuerySnapshots() # Snapshots
        vss_sets = []
        if self.debug:
            print(f'found {len(snaps)} snapshots')

        set_ids = []
        for snap in snaps:
            if snap.SnapshotSetId not in set_ids:
                set_ids.append(snap.SnapshotSetId)
        if self.debug:
            print(f'found {len(set_ids)} snapshotsets')

        for set_id in set_ids:
            vss_set = VSSSnapshotSet(provider=self, set_id=set_id, operation='query', context=self.context, debug=self.debug)
            vss_sets.append(vss_set)
        del cmp

        # returning a list of the "snapshot sets" (snapshots are a sub-object of the snapshot set)
        return vss_sets


class VSSSnapshot(object):
    '''
        This is a VolumeShadowCopyService ShadowCopy (single Shadow Copy created for a whole drive)

        Note: This is a subclass handled by the VSSSnapshotSet class

        Individual operations like exposing/unexposing the snapshot are done here
    '''
    def __init__(self, snap_id:object, operation:str, volume_name:str='', components:object=None, set_id:object=None,
                 snap_object:object=None, context=Backup, provider:object=None, debug=False):
        self.snap_object = snap_object
        self.volume_name = volume_name
        if snap_id and isinstance(snap_id, str):
            # you can pass the snap_id guid as a string, and we will make the correct Guid object out of it
            try:
                snap_id = Guid.Parse(snap_id)
            except System.FormatException as e:
                raise Exception(f"GUID styled string not passed for snap_id: '{snap_id}' ! like 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'") from e

        self.snap_id = snap_id
        self.debug = debug
        self.operation = operation
        self.initialized_for = None
        self.context = context
        self.operation = operation
        self.exposed_path = None
        if self.operation.lower() not in ['backup', 'restore', 'query']:
            raise Exception(f'Provider Operation is not valid: {operation}')
        if set_id:
            self.set_id = set_id
        else:
            set_id = None

        if not provider:
            self.provider = VSSProvider(context=context, operation=operation, debug=debug)
        else:
            self.provider = provider # VSSProvider object

        self.components = components
        if not components:
            if self.debug:
                print('Creating components from VSSSnapshot object!')
            components = self.provider.create_backup_components()
            self.components = components

        if self.debug:
            vol_name = volume_name[:2] # truncate the '\\'
            print(f'VSSSnapshot object of {vol_name} created')

        self.provider._initialize(components)
        if operation.lower() == 'backup':
            if not self.volume_name:
                volume_name = self.get_drive_letter()
                if not volume_name:
                    raise Exception('getting volume for snapshot set didnt match volume to snapshot id')

                self.volume_name = volume_name
                if not components.IsVolumeSupported(volume_name):
                    raise Exception(f'Volume {volume_name} is not supported for {self.operation.capltalize()}')

    def get_drive_letter(self):
        '''
            Find the drive letter for the specific SnapshotID you are trying to work with
            This helps build the VSSSnapshot when you are trying to run query_snapshot()
        '''
        for key, item in get_drives().items():
            if item == self.snap_id.ToString():
                if self.debug:
                    print(f'found drive letter for DeviceID: {key} --> {item}')
                volume_name = f'{key}\\'
                return volume_name

        return None

    def expose_snapshot(self, expose_path:str, attributes=ExposedLocally, path_from_root=None):
        '''
            expose_path: (str, required) the path you want to expose the snapshot as
                ex. R:\\,
                    R:\\thisdir\\

                    ... or ...

                    a valid windows share name (in the case of attributes=ExposedRemotely)

            path_from_root: (str) where in the snapshot do you want to set the root path to (only for .ExposedRemotely)
                * example: \\Windows (where \\Windows is a valid subdirectory of the snapshot)
            attributes: .ExposedLocally (default), or .ExposedRemotely
                * ExposedRemotely creates a share the snapshot is accessible from, and allows usage of path_from_root
                * ExposedLocally requires expose_path and takes arguments like:
                    'R:\\'  where R: DOES NOT ALREADY EXIST and is a valid windows drive letter root path
                    'C:\\temp\\exposedsnapshot'  where the drive/directory already exists and is empty
                                                (ExposeSnapshot creates a junction point to the snapshot)


        '''

        # Note to self:  You have to go through a QuerySnapshot cycle and use the components that were created for the query to Expose the snapshot locally
        # Theoretically, it might be possible with the Backup "components" object since it created the Snapshot set but we will see

        remotely = None
        if attributes & ExposedLocally == ExposedLocally:
            remotely = False
            # path_from_root is not usable in locally exposed snapshots..  the whole snapshot is exposed
            path_from_root = None
        elif attributes & ExposedRemotely == ExposedRemotely:
            remotely = True
            if ':' in expose_path or '\\' in expose_path or '/' in expose_path:
                # $ is okay in share name in fact, thisshare$ hides the share name so it is not broadcasted to the world browsing it
                raise Exception('Exposing a Snapshot Remotely with a colon, slash or backslash in the share name is not advised')

        cmp = self.components

        if len(expose_path) > 3 and not exists(expose_path) and remotely is False:
            raise Exception('Unable to expose a snapshot to a directory that does not exist')
        elif len(expose_path) > 2 and not expose_path.endswith('\\') and remotely is False:
            expose_path += '\\'
        elif len(expose_path) == 2 and not expose_path[:1].is_alpha():
            # ex: 4:  4 is not a drive letter
            raise Exception('Exposing a Snapshot Locally with a non-alphabetic drive letter is prohibited: {expose_path[:1]}')
        elif remotely is not True and len(expose_path) == 2 and expose_path[1:] != ":":
            # ex: A$  $ needs to be a colon (when exposing locally)  A$ is a viable share name if remotely sharing the snapshot
            raise Exception('Exposing a Snapshot Locally without a colon after the drive letter is prohibited: {expose_path[1:]}')

        elif self.operation.lower() not in ['backup', 'expose', 'query']:
            raise Exception(f'The components object was initialized for something other than \'Backup\', \'Query\', or \'Expose\' != {self.operation}')
        if self.debug:
            print(f'expose_snapshot: Exposing -> {self.snap_id} to {expose_path} -> {snapshot_attr_names[attributes]}')
        try:
            exposed_path = cmp.ExposeSnapshot(self.snap_id, path_from_root, attributes, expose_path)
            if not exposed_path == expose_path:
                raise Exception('Exposing Snapshot did not return what we expected: {exposed_path} != {expose_path}')
            self.exposed_path = exposed_path
            if remotely:
                print(f'Exposed {self.snap_id}  to {expose_path} Remotely using path_from_root = {path_from_root}')
            else:
                print(f'Exposed {self.snap_id}  to {expose_path} Locally')

        except alphavsslib.VssObjectAlreadyExistsException:
            print('The object is already exposed!')
            return False
        except alphavsslib.VssBadStateException:
            print('Bad State Exception: {self.snap_id}')
            return False
        except alphavsslib.VssObjectNotFoundException:
            # Typically a problem with running cmp.QuerySnapshots() or
            #      cmp.InitializeForBackup() or
            #      a bad/incorect context sent to the provider
            print('Snapshot not found by AlphaVSS: {self.snap_id}')
            return False

        return True

    def unexpose_snapshot(self):
        '''
            Unexpose a snapshot (local or remote) from the local system
        '''
        cmp = self.components
        try:
            cmp.UnexposeSnapshot(self.snap_id)
        except Exception as e:
            raise Exception('Error unexposing snapshot: {e}') from e

        if self.debug:
            print(f'Unexposed snapshot id: {self.snap_id} from {self.exposed_path}')

        self.exposed_path = None

        return True


class VSSSnapshotSet(object):
    '''
        This is a VolumeShadowCopy Set (collection of multiple Shadow Copies created at an exact moment in time)

        A VSSSnapshotSet is the top level object in a Volume ShadowCopy Object containing one or more VSSSnapshot ShadowCopy objects

        Note: Default Snapshot creation is to make "Non-Persistent" Snapshot Sets (they will not persist across reboots or after your python
              application closes)
              If this is not what you want, you can change the Context to be (or something similar) in the VSSProvider:
                    alphavsslib.VssSnapshotContext.AppRollback (which includes persistence)
    '''
    def __init__(self, volume_names:list=None, provider:object=None, system_state:bool=True, component_mode:bool=False,
                 partial_file_support:bool=False, operation:str='backup', backup_type:int=alphavsslib.VssBackupType.Full,
                 context:int=Backup, set_id=None, snapshots:list=None, components:object=None, debug:bool=False):
        '''
            volume_names: (list) ex. ['C:\\', 'D:\\', 'F:\\']
            provider: (object, optional) VSSProvider object, If you are querying snapshots from the VSSProvider object, the provider object gets passed in,
                               otherwise, it's created on the fly
            system_state: (bool) Backup the System State (True) or not (False).
            component_mode: (bool) allows you to turn off certain VSS backup writers (only tested with component_mode=False -- more work needed).
                            more work would need to be done to implement the turning on and off of various writers
            partial_file_support: (bool) only tested with False.
            backup_type: (int) only tested with alphavss.VssBackupType.Full
            context: (int, default = 0 [Backup]) allows us to define different snapshot conext options (like Persistence across reboots AKA AppRollback)
            components: (object) only here in case you've created this object from a VSSProvider object
            debug: (bool) enables enhanced output
        '''
        self.operations = ['backup', 'restore', 'query']
        self.debug = debug
        # volume_names could be None in case of query (and dynamically built below)
        self.volume_names = volume_names
        self.context = context
        self.initialized_for = None
        self.set_id = None
        if set_id and isinstance(set_id, str):
            try:
                set_id = Guid.Parse(set_id)
            except System.FormatException as e:
                raise Exception(f"GUID styled string not passed for set_id: '{set_id}' ! like 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'") from e

        if set_id:
            self.set_id = set_id
        self.snapshots = None
        if snapshots:
            self.snapshots = snapshots
        if operation.lower() not in self.operations:
            raise Exception(f'Unable to determine VSSSnapshotSet operation to perform: {operation}')
        self.operation = operation.lower()
        self.system_state = system_state
        self.partial_file_support = partial_file_support
        if component_mode is True:
            # more work is needed to support component mode = True (leaving all the VSS writers active isnt a bad thing)
            print('untested / uncoded configuration with component_mode = True')
        self.component_mode = component_mode
        self.backup_type = backup_type

        if not provider:
            self.provider = VSSProvider(debug=debug)
        else:
            self.provider = provider

        if not components:
            if self.debug:
                print('creating components from VSSSnapshotSet!')
            components = self.provider.create_backup_components()
        else:
            if self.provider.initialized_for:
                self.initialized_for = self.provider.initialized_for

        self.snapshots = []
        self.provider._initialize(components)
        if operation.lower() == 'backup':
            if not self.volume_names:
                volume_names = self.get_volume_names()
                if len(volume_names) != len(self.snapshots):
                    raise Exception('getting volumes for snapshot set didnt match all volumes to snapshots')
                else:
                    self.volume_names = volume_names
            for volume_name in self.volume_names:
                if not components.IsVolumeSupported(volume_name):
                    raise Exception(f'Volume {volume_name} is not supported for {self.operation.capltalize()}')
            self.backup(components)
        elif operation.lower() == 'delete':
            self.delete(components)
        elif operation.lower() == 'query':
            self.query(set_id, components=components)

    def get_volume_names(self):
        '''
            Match up the Snapshot OriginalVolumeName to the Drive letter for the snapshot

            This helps build the VSSSnapshotSet when you are trying to run query_snapshot()
        '''
        volume_names = []
        for snap in self.snapshots:
            for key, item in get_drives().items():
                if item == snap.OriginalVolumeName:
                    found_letters += 1
                    print(f'found drive letter for DeviceID: {key} --> {item}')
                    volume_name = f'{key}\\'
                    volume_names.append(volume_name)
        if len(self.snapshots) != len(volume_names):
            raise Exception('The number of volume names doesnt match the number of snapshots')

        return volume_names


    def get_volume_name(self, snapshot_id):
        '''
            Find the volume name for the specific SnapshotID you are trying to work with

            This helps build the VSSSnapshot when you are trying to run query_snapshot()
        '''
        for snap in self.snapshots:
            if snapshot_id == snap.SnapshotId:
                for key, item in get_drives().items():
                    if item == snap.OriginalVolumeName:
                        if self.debug:
                            print(f'found drive letter for DeviceID: {key} --> {item}')
                        volume_name = f'{key}\\'
                        return volume_name

        raise Exception(f'Did not find the volume name of the snapshot id: {snapshot_id.ToString()}')


    def backup(self, components):
        '''
            Once you've validated all the drives that you want to snapshot, create all individual shadow copies at once
            ex.  ['C:\\' , 'D:\\', 'G:\\'] in order to get a consistent representation of the application states that might
            span multiple drives (MS SQL Server for one could have databases/logs on multiple drives with LOGS on one drive
            and MDF files on another drive --  standard practice for highly performant databases)
        '''

        set_id = components.StartSnapshotSet()
        self.set_id = Guid.Parse(set_id)
        if self.debug:
            print(f'set_id ->> {set_id}')

        for volume_name in self.volume_names:
            # we validated the volumes in _prepare
            snap_id = components.AddToSnapshotSet(volume_name)
            snap_id = Guid.Parse(snap_id)
            if self.debug:
                print(f'snap_id ->> {snap_id} == {volume_name}')
            snapshot = VSSSnapshot(volume_name=volume_name, set_id=set_id, snap_id=snap_id, operation=self.operation, provider=self.provider, debug=self.debug)
            self.snapshots.append(snapshot)

        components.SetBackupState(self.component_mode, self.system_state, self.backup_type, self.partial_file_support)
        components.PrepareForBackup()
        components.DoSnapshotSet()

        if self.debug:
            volumes =  ', '.join(name[:2] for name in self.volume_names) # truncate the '\\' on volume_name
            print(f'Successfully created the snapshot(s) for volume(s): {volumes} as snapshot set id: {self.set_id}')
            print('    Snapshot(s):')
            for snap in self.snapshots:
                print(f'        Volume: {snap.volume_name} -> snapshot id: {snap.snap_id}')


        return True


    def delete(self, components, force_delete=False):
        '''
            Delete all the shadow copies in this Shadow Copy Set
        '''
        num_of_deletes = 0
        num_of_deletes = components.DeleteSnapshotSet(self.set_id, force_delete)

        # I believe this is the number of snapshot deletes...  not set deletes
        return num_of_deletes

    def query(self, set_id, components=None):
        '''
            Query the existing Snapshots on the system

            context:
                https://github.com/alphaleonis/AlphaVSS/blob/13462e657f7993da5c80f835d219bbe82079ce75/src/AlphaVSS.Common/Enumerations/VssSnapshotContext.cs

                Note: context can be a combination of the VssSnapshotContext options and
                      VssVolumeSnapshotArrtibutes options ORed together
                .Backup = 0
                .All = 4294967295  # Doesn't work because of an INT conversion issue in .NET and/or pythonnet
                    # Seems related: https://github.com/pythonnet/pythonnet/issues/950
                .ClientAccessibleWriters = 13
                .ClientAccessible = 29
                .AppRollback = 9 (Persistent (1) + NoAutoRelease(8))
                .NasRollback = 25 (NoWriters/FileShareBackup + Persistent + NoAutoRelease)
                .FileShareBackup = 16 (= .NoWriters)

                alphavsslib.VssVolumeSnapshotAttributes.Persistent = 1
                alphavsslib.VssVolumeSnapshotAttributes.NoAutoRelease = 8
        '''
        snaps = components.QuerySnapshots() # list of snapshots

        snapshots = []
        vol_names = []
        if self.debug:
            print(f'looking for set_id: {set_id} in {len(snaps)} snapshot(s)')
        for snap in snaps:
            if snap.SnapshotSetId == set_id:
                if self.debug:
                    print(f'found correct SnapshotSetId = {snap.SnapshotSetId}')
                drive_letter = self.find_drive_letter_for_volume_id(snap.OriginalVolumeName)
                if not drive_letter:
                    raise Exception(f'Unable to find Volume Name for Snapshot ID: {snap.SnapshotId.ToString()}')
                vss_snap = VSSSnapshot(provider=self.provider, operation='query', set_id=snap.SnapshotSetId, snap_id=snap.SnapshotId, snap_object=snap, context=self.context, volume_name=drive_letter, debug=self.debug)
                vol_names.append(drive_letter)
                snapshots.append(vss_snap)

        self.snapshots = snapshots
        self.volume_names = vol_names

        if snaps:
            return True
        else:
            if self.debug:
                print('possible error querying snapshot set: none were found (did you specify the correct context?)')
            return None

    def find_drive_letter_for_volume_id(self, volume_id:str):
        '''
            Find the volume name of a snapshot given the Volume ID

            examples from get_drives():  # unique to every system (unless cloned)

            {'C:': '\\\\?\\Volume{3f422e46-1e27-4436-872b-e2f2eea8102b}\\',
             'D:': '\\\\?\\Volume{3cbee176-7af0-4a8b-b498-44b51afbc3c7}\\',
             'F:': '\\\\?\\Volume{61eb9eea-9578-4c9e-b3ef-a2c4269bedd9}\\'}
        '''
        for key, item in get_drives().items():
            if item == volume_id:
                if self.debug:
                    print(f'found drive letter for the Volume: {key} --> {item}')
                volume_name = f'{key}\\' # 'X:\\'
                return volume_name

        return False


def get_drives(filter_letter:str=None):
    '''
        Kind of have to temporarily use WMI for this.
            We need a Volume DeviceID to DriveLetter mapping
            When we query a Snapshot Set, it gives us DeviceIDs, and not letters like when we create a snapshotset of drives, or expose them.

        https://github.com/alphaleonis/AlphaFS/blob/develop/src/AlphaFS/Device/Volume/Volume.GetVolumeDisplayName.cs

        I believe this would replace the WMI code but for now, WMI does the job fine
    '''
    volumes = {}
    c = wmi.WMI()
    # DriveType = 3 == Fixed Disks
    #   (for now, testing limited to Fixed Disks, unsure of viability of other disk types for purposes of snapshots)
    for vol in c.query("SELECT * FROM Win32_Volume WHERE DriveType = 3"):
        letter = vol.wmi_property('DriveLetter').value
        device_id = vol.wmi_property('DeviceID').value
        if letter and letter not in volumes:
            if filter_letter and filter_letter.lower() != letter.lower():
                continue
            volumes[letter.upper()] = device_id

    return volumes
