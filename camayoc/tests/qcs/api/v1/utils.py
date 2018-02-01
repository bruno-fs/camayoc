# coding=utf-8
"""Shared utility functions for v1 tests."""

import pprint
import time

from camayoc import config
from camayoc.exceptions import (
    WaitTimeError,
    FailedScanException,
    ConfigFileNotFoundError,
)
from camayoc.qcs_models import (
    Credential,
    Source,
    Scan
)


def wait_until_state(scan, timeout=120, state='completed'):
    """Wait until the scan has failed or reached desired state.

    The default state is 'completed'.

    This method should not be called on scan jobs that have not yet been
    created, are paused, or are canceled.

    The default timeout is set to 120 seconds, but can be overridden if it is
    anticipated that a scan may take longer to complete.
    """
    while (
            not scan.status() or not scan.status() == state) and timeout > 0:
        time.sleep(5)
        timeout -= 5
        if timeout <= 0:
            raise WaitTimeError(
                'You have called wait_until_state() on a scan with ID={} and\n'
                'the scan timed out while waiting to achieve the state="{}"\n'
                'When the scan timed out, it had the state="{}".\n'
                'The full details of the scan were \n{}\n'
                'The "results" available from the scan were \n{}\n'
                .format(
                    scan._id,
                    state,
                    scan.status(),
                    pprint.pformat(scan.read().json()),
                    pprint.pformat(scan.results().json()),
                )
            )
        if state != 'failed' and scan.status() == 'failed':
            raise FailedScanException(
                'You have called wait_until_state() on a scan with ID={} and\n'
                'the scan failed instead of acheiving state={}.\n'
                'When it failed, the details about the scan were \n{}\n'
                'The "results" available from the scan were \n{}\n'
                .format(
                    scan._id,
                    state,
                )
            )


def network_sources():
    """Gather sources from config file.

    If no config file is found, or no sources defined,
    then an empty list will be returned.

    If a test is parametrized on the sources in the config file, it will skip
    if no sources are found.
    """
    try:
        srcs = [s for s in config.get_config()['qcs']['sources']
                if s['type'] == 'network']
    except (ConfigFileNotFoundError, KeyError):
        srcs = []
    return srcs


def first_network_source():
    """Gather sources from config file.

    If no source is found in the config file, or no config file is found, a
    default source will be returned.
    """
    try:
        for s in config.get_config()['qcs']['sources']:
            if s['type'] == 'network':
                src = [s]
                break
    except (ConfigFileNotFoundError, KeyError):
        src = [
            {
                'hosts': ['localhost'],
                'name':'localhost',
                'credentials':'root'
            }
        ]
    return src


def prep_broken_scan(source_type, cleanup, scan_type='inspect'):
    """Return a scan that can be created but will fail to complete.

    Create and return a source with a non-existent host and dummy credential.
    It is returned ready to be POSTed to the server via the create() instance
    method.
    """
    bad_cred = Credential(
        username='broken',
        password='broken',
        cred_type=source_type
    )
    bad_cred.create()
    cleanup.append(bad_cred)
    bad_src = Source(
        source_type=source_type,
        hosts=['1.0.0.0'],
        credential_ids=[bad_cred._id],
    )
    bad_src.create()
    cleanup.append(bad_src)
    bad_scn = Scan(
        source_ids=[bad_src._id],
        scan_type=scan_type,
    )
    return bad_scn


def prep_network_scan(source, cleanup, client, scan_type='inspect'):
    """Given a source from config file, prep the scan.

    Takes care of creating the Credential and Source objects on the server and
    staging them for cleanup after the tests complete.
    """
    cfg = config.get_config()
    cred_ids = []
    for c in cfg['credentials']:
        if c['name'] in source['credentials'] and c['type'] == 'network':
            cred = Credential(
                cred_type='network',
                client=client,
                username=c['username'],
            )
            if c.get('sshkeyfile'):
                cred.ssh_keyfile = c['sshkeyfile']
            else:
                cred.password = c['password']
            cred.create()
            cleanup.append(cred)
            cred_ids.append(cred._id)

    netsrc = Source(
        source_type='network',
        client=client,
        hosts=source['hosts'],
        credential_ids=cred_ids,
    )
    netsrc.create()
    cleanup.append(netsrc)
    scan = Scan(source_ids=[netsrc._id], scan_type=scan_type)
    return scan