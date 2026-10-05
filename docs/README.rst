.. _readme:

incus-formula
=============

|img_sr| |img_pc|

.. |img_sr| image:: https://img.shields.io/badge/%20%20%F0%9F%93%A6%F0%9F%9A%80-semantic--release-e10079.svg
   :alt: Semantic Release
   :scale: 100%
   :target: https://github.com/semantic-release/semantic-release
.. |img_pc| image:: https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white
   :alt: pre-commit
   :scale: 100%
   :target: https://github.com/pre-commit/pre-commit

A SaltStack formula for installing and managing `Incus <https://linuxcontainers.org/incus/>`_,
a container and virtual machine hypervisor (fork of LXD).

Manages Incus installation from Zabbly repositories, LXCFS configuration,
server settings, images, networks (including ACLs, forwards, peers, zones),
storage (pools, volumes, snapshots, attachments), profiles, instances
(with cloud-init support), instance snapshots with rotation policies,
and TLS client certificate management.

.. contents:: **Table of Contents**
   :depth: 1

General notes
-------------

See the full `SaltStack Formulas installation and usage instructions
<https://docs.saltproject.io/en/latest/topics/development/conventions/formulas.html>`_.

If you are interested in writing or contributing to formulas, please pay attention to the `Writing Formula Section
<https://docs.saltproject.io/en/latest/topics/development/conventions/formulas.html#writing-formulas>`_.

If you want to use this formula, please pay attention to the ``FORMULA`` file and/or ``git tag``,
which contains the currently released version. This formula is versioned according to `Semantic Versioning <http://semver.org/>`_.

See `Formula Versioning Section <https://docs.saltproject.io/en/latest/topics/development/conventions/formulas.html#versioning>`_ for more details.

If you need (non-default) configuration, please refer to:

- `how to configure the formula with map.jinja <map.jinja.rst>`_
- the ``pillar.example`` file
- the `Special notes`_ section

Contributing to this repo
-------------------------

Commit messages
^^^^^^^^^^^^^^^

**Commit message formatting is significant!!**

Please see `How to contribute <https://github.com/saltstack-formulas/.github/blob/master/CONTRIBUTING.rst>`_ for more details.

pre-commit
^^^^^^^^^^

`pre-commit <https://pre-commit.com/>`_ is configured for this formula, which you may optionally use to ease the steps involved in submitting your changes.
First install  the ``pre-commit`` package manager using the appropriate `method <https://pre-commit.com/#installation>`_, then run ``bin/install-hooks`` and
now ``pre-commit`` will run automatically on each ``git commit``. ::

  $ bin/install-hooks
  pre-commit installed at .git/hooks/pre-commit
  pre-commit installed at .git/hooks/commit-msg

Special notes
-------------

This formula uses custom Salt execution and state modules:

- ``incus`` -- state module for managing Incus resources (instances, networks, storage, etc.)
- ``incus_pki`` -- state module for TLS certificate generation and trust management

Sync custom modules before first apply::

  salt '<minion>' saltutil.sync_all

TLS states (``incus.tls``) are not included in the main ``incus`` meta-state
and must be applied separately::

  salt '<minion>' state.apply incus.tls

Available states
----------------

.. contents::
   :local:

``incus``
^^^^^^^^^

*Meta-state (This is a state that includes other states)*.

Installs the Incus package (with optional Zabbly repository setup),
starts the service, runs initial configuration, then applies all
resource states: LXCFS, server settings, images, networks, storage,
profiles, instances, and instance snapshots.

``incus.package``
^^^^^^^^^^^^^^^^^

Installs the Incus package and dependencies. Configures the Zabbly APT/YUM
repository if ``repo.enable`` is set. Starts and enables the ``incus`` service.
Runs ``incus admin init --minimal`` on first install.

``incus.lxcfs``
^^^^^^^^^^^^^^^

Manages the LXCFS systemd service override for Incus. Configures enabled
modules (loadavg, cfs, memory, cpuset, sysinfo, pidfd) and restarts the
service on changes. Only applied when ``global.lxcfs.enable`` is ``true``.

``incus.settings``
^^^^^^^^^^^^^^^^^^

Manages Incus server configuration. Supports three modes:

- Bulk settings via ``server_settings.config`` (merged with existing)
- Individual settings via ``server_settings_individual`` (present/absent)
- Managed settings via ``server_settings.managed_config`` (exact match, replaces all)

``incus.images``
^^^^^^^^^^^^^^^^

Manages Incus images from remote sources (e.g., ``images.linuxcontainers.org``).
Supports auto-update, public/private visibility, aliases, and custom properties.

``incus.networks``
^^^^^^^^^^^^^^^^^^

Manages Incus networking resources:

- Networks (bridge, macvlan, etc.)
- Network ACLs (ingress/egress rules)
- Network forwards (port forwarding)
- Network peers (network peering)
- Network zones and zone records (DNS)

``incus.storage``
^^^^^^^^^^^^^^^^^

Manages Incus storage resources:

- Storage pools (dir, zfs, btrfs, lvm, ceph)
- Storage volumes with config updates
- Volume snapshots
- Volume attachments to instances

``incus.profiles``
^^^^^^^^^^^^^^^^^^

Manages Incus profiles with config, devices, and descriptions.
Supports config-only updates and profile removal.

``incus.instances``
^^^^^^^^^^^^^^^^^^^

Manages Incus instance lifecycle:

- Create instances (containers or VMs) from images
- Start instances with optional readiness checks
- Wait for cloud-init initialization
- Restart instances (stop + start)

``incus.instance-snapshots``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Manages instance snapshots with multiple strategies:

- Basic snapshots (present/absent/restored)
- Managed snapshots with automatic rotation policies
- Standalone snapshot rotation by pattern and retention count

``incus.tls``
^^^^^^^^^^^^^

Manages TLS client certificates for Incus API access.
**Not included in the main meta-state** -- must be applied separately.

Includes two sub-states:

- ``incus.tls.generate`` -- generates a client key pair
- ``incus.tls.trust`` -- imports the certificate into Incus trust store

``incus.clean``
^^^^^^^^^^^^^^^

*Meta-state (This is a state that includes other states)*.

Stops the Incus service, disables it, and removes the package.
Removes the LXCFS systemd override.

Resource cleanup states (networks, storage, instances, etc.) are
intentionally empty to prevent accidental data loss.

``incus.package.clean``
^^^^^^^^^^^^^^^^^^^^^^^

Stops the Incus service and removes the package.

``incus.lxcfs.clean``
^^^^^^^^^^^^^^^^^^^^^

Stops the LXCFS service and removes the systemd override directory.

Testing
-------

Linux testing is done with ``kitchen-salt``.

Requirements
^^^^^^^^^^^^

* Ruby
* Docker

.. code-block:: bash

   $ gem install bundler
   $ bundle install
   $ bin/kitchen test [platform]

Where ``[platform]`` is the platform name defined in ``kitchen.yml``,
e.g. ``debian-13-master-py3``.

``bin/kitchen converge``
^^^^^^^^^^^^^^^^^^^^^^^^

Creates the docker instance and runs the ``incus`` main state, ready for testing.

``bin/kitchen verify``
^^^^^^^^^^^^^^^^^^^^^^

Runs the ``inspec`` tests on the actual instance.

``bin/kitchen destroy``
^^^^^^^^^^^^^^^^^^^^^^^

Removes the docker instance.

``bin/kitchen test``
^^^^^^^^^^^^^^^^^^^^

Runs all of the stages above in one go: i.e. ``destroy`` + ``converge`` + ``verify`` + ``destroy``.

``bin/kitchen login``
^^^^^^^^^^^^^^^^^^^^^

Gives you SSH access to the instance for manual testing.
