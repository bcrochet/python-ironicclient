#
#   Copyright 2015 Red Hat, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
#

import argparse
import logging

from cliff import command
from cliff import lister
from cliff import show
from openstackclient.common import utils as oscutils
import six

from ironicclient.common.i18n import _
from ironicclient.common import utils
from ironicclient import exc
from ironicclient.v1 import resource_fields as res_fields


class ListBaremetal(lister.Lister):
    """List baremetal nodes"""

    log = logging.getLogger(__name__ + ".ListBaremetal")

    def get_parser(self, prog_name):
        parser = super(ListBaremetal, self).get_parser(prog_name)
        parser.add_argument(
            '--limit',
            metavar='<limit>',
            type=int,
            help='Maximum number of nodes to return per request, '
                 '0 for no limit. Default is the maximum number used '
                 'by the Baremetal API Service.'
        )
        parser.add_argument(
            '--marker',
            metavar='<node>',
            help='Node UUID (for example, of the last node in the list from '
                 'a previous request). Returns the list of nodes after this '
                 'UUID.'
        )
        parser.add_argument(
            '--sort',
            metavar="<key>[:<direction>]",
            help='Sort output by selected keys and directions(asc or desc) '
                 '(default: asc), multiple keys and directions can be '
                 'specified separated by comma',
        )
        parser.add_argument(
            '--maintenance',
            dest='maintenance',
            action='store_true',
            default=False,
            help="List nodes in maintenance mode.",
        )
        parser.add_argument(
            '--associated',
            dest='associated',
            action='store_true',
            default=False,
            help="List nodes by instance association."
        )
        parser.add_argument(
            '--detail',
            dest='detail',
            action='store_true',
            default=False,
            help="Show detailed information about the nodes."
        )
        parser.add_argument(
            '--long',
            dest='detail',
            action='store_true',
            default=False,
            help="Show detailed information about the nodes. "
                 "Alias for --detail.",
        )
        return parser

    def take_action(self, parsed_args):
        self.log.debug("take_action(%s)" % parsed_args)
        client = self.app.client_manager.baremetal

        columns = tuple(res_fields.NODE_LIST_FIELD_LABELS)

        params = {}
        if parsed_args.limit is not None and parsed_args.limit < 0:
            raise exc.CommandError(
                _('Expected non-negative --limit, got %s') %
                parsed_args.limit)
        params['limit'] = parsed_args.limit
        params['marker'] = parsed_args.marker
        if parsed_args.associated:
            params['associated'] = parsed_args.associated
        if parsed_args.maintenance:
            params['maintenance'] = parsed_args.maintenance

        if parsed_args.detail:
            columns = tuple(res_fields.NODE_FIELD_LABELS)
        params['detail'] = parsed_args.detail

        data = client.node.list(**params)

        data = oscutils.sort_items(data, parsed_args.sort)

        return (columns,
                (oscutils.get_item_properties(s, columns, formatters={
                    'Properties': oscutils.format_dict},) for s in data))


class ShowBaremetal(show.ShowOne):
    """Show baremetal node details"""

    log = logging.getLogger(__name__ + ".ShowBaremetal")
    LONG_FIELDS = [
        'extra',
        'properties',
        'ports',
        'driver_info',
        'driver_internal_info'
    ]

    def get_parser(self, prog_name):
        parser = super(ShowBaremetal, self).get_parser(prog_name)
        parser.add_argument(
            "node",
            metavar="<node>",
            help="Name or UUID of the node (or instance UUID if --instance "
                 "is specified)")
        parser.add_argument(
            '--instance',
            dest='instance_uuid',
            action='store_true',
            default=False,
            help='<node> is an instance UUID.')
        parser.add_argument(
            '--long',
            action='store_true')
        return parser

    def take_action(self, parsed_args):
        self.log.debug("take_action(%s)", parsed_args)

        baremetal_client = self.app.client_manager.baremetal
        if parsed_args.instance_uuid:
            node = baremetal_client.node.get_by_instance_uuid(
                parsed_args.node)._info
        else:
            node = oscutils.find_resource(baremetal_client.node,
                                          parsed_args.node)._info
        node.pop("links", None)
        if not parsed_args.long:
            for field in self.LONG_FIELDS:
                node.pop(field, None)

        return zip(*sorted(six.iteritems(node)))


class DeleteBaremetal(command.Command):
    """Unregister a baremetal node"""

    log = logging.getLogger(__name__ + ".DeleteBaremetal")

    def get_parser(self, prog_name):
        parser = super(DeleteBaremetal, self).get_parser(prog_name)
        parser.add_argument(
            "node",
            metavar="<node>",
            help="Node to delete (name or ID)")

        return parser

    def take_action(self, parsed_args):
        self.log.debug("take_action(%s)", parsed_args)

        baremetal_client = self.app.client_manager.baremetal

        node = oscutils.find_resource(baremetal_client.node,
                                      parsed_args.node)
        baremetal_client.node.delete(node.uuid)


class CreateBaremetal(show.ShowOne):
    """Register a new node with the baremetal service"""

    log = logging.getLogger(__name__ + ".CreateBaremetal")

    def get_parser(self, prog_name):
        parser = super(CreateBaremetal, self).get_parser(prog_name)

        parser.add_argument(
            '--chassis',
            dest='chassis_uuid',
            metavar='<chassis>',
            help='UUID of the chassis that this node belongs to.')
        parser.add_argument(
            '--chassis_uuid',
            help=argparse.SUPPRESS)
        parser.add_argument(
            '-d', '--driver',
            metavar='<driver>',
            required=True,
            help='Driver used to control the node [REQUIRED].')
        parser.add_argument(
            '-i', '--driver-info',
            metavar='<key=value>',
            action='append',
            help='Key/value pair used by the driver, such as out-of-band '
                 'management credentials. Can be specified multiple times.')
        parser.add_argument(
            '--driver_info',
            action='append',
            help=argparse.SUPPRESS)
        parser.add_argument(
            '-p', '--properties',
            metavar='<key=value>',
            action='append',
            help='Key/value pair describing the physical characteristics of '
                 'the node. This is exported to Nova and used by the '
                 'scheduler. Can be specified multiple times.')
        parser.add_argument(
            '-e', '--extra',
            metavar='<key=value>',
            action='append',
            help="Record arbitrary key/value metadata. "
                 "Can be specified multiple times.")
        parser.add_argument(
            '-u', '--uuid',
            metavar='<uuid>',
            help="Unique UUID for the node.")
        parser.add_argument(
            '-n', '--name',
            metavar='<name>',
            help="Unique name for the node.")

        return parser

    def take_action(self, parsed_args):
        self.log.debug("take_action(%s)", parsed_args)

        baremetal_client = self.app.client_manager.baremetal

        field_list = ['chassis_uuid', 'driver', 'driver_info',
                      'properties', 'extra', 'uuid', 'name']
        fields = dict((k, v) for (k, v) in vars(parsed_args).items()
                      if k in field_list and not (v is None))
        fields = utils.args_array_to_dict(fields, 'driver_info')
        fields = utils.args_array_to_dict(fields, 'extra')
        fields = utils.args_array_to_dict(fields, 'properties')
        node = baremetal_client.node.create(**fields)._info

        node.pop('links', None)

        return zip(*sorted(six.iteritems(node)))


class SetBaremetal(show.ShowOne):
    """Set baremetal properties"""

    log = logging.getLogger(__name__ + ".SetBaremetal")

    def get_parser(self, prog_name):
        parser = super(SetBaremetal, self).get_parser(prog_name)

        parser.add_argument(
            'node',
            metavar='<node>',
            help="Name of UUID of the node."
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing attribute',
        )
        parser.add_argument(
            'properties',
            metavar='<path=value>',
            nargs='+',
            action='append',
            default=[],
            help="Property to set or update. Can be specified "
                 "multiple times.")

        return parser

    def take_action(self, parsed_args):
        self.log.debug("take_action(%s)", parsed_args)

        baremetal_client = self.app.client_manager.baremetal

        if (not parsed_args.node
                and not parsed_args.properties
                and not parsed_args.update):
            return

        op = 'replace' if parsed_args.update else 'add'

        patch = utils.args_array_to_patch(op, parsed_args.properties[0])
        node = baremetal_client.node.update(parsed_args.node, patch)._info

        node.pop("links", None)

        return zip(*sorted(six.iteritems(node)))


class UnsetBaremetal(show.ShowOne):
    """Unset baremetal properties"""
    log = logging.getLogger(__name__ + ".UnsetBaremetal")

    def get_parser(self, prog_name):
        parser = super(UnsetBaremetal, self).get_parser(prog_name)

        parser.add_argument(
            'node',
            metavar='<node>',
            help="Name of UUID of the node."
        )
        parser.add_argument(
            'properties',
            metavar='<path=value>',
            nargs='+',
            action='append',
            default=[],
            help="Property to set or update. Can be specified "
                 "multiple times.")

        return parser

    def take_action(self, parsed_args):
        self.log.debug("take_action(%s)", parsed_args)

        baremetal_client = self.app.client_manager.baremetal

        if not parsed_args.node and not parsed_args.properties:
            return

        patch = utils.args_array_to_patch('remove', parsed_args.properties[0])
        node = baremetal_client.node.update(parsed_args.node, patch)._info

        node.pop("links", None)

        return zip(*sorted(six.iteritems(node)))


class RebootBaremetal(command.Command):
    """Reboot baremetal system"""

    log = logging.getLogger(__name__ + ".RebootBaremetal")

    def get_parser(self, prog_name):
        parser = super(RebootBaremetal, self).get_parser(prog_name)

        parser.add_argument(
            'node',
            metavar='<node>',
            help="Name or UUID of the node.")

        return parser

    def take_action(self, parsed_args):
        self.log.debug("take_action(%s)", parsed_args)

        baremetal_client = self.app.client_manager.baremetal

        baremetal_client.node.set_power_state(
            parsed_args.node, 'reboot')


class PowerBaremetal(command.Command):
    """Set power state of baremetal system"""

    log = logging.getLogger(__name__ + ".PowerBaremetal")

    def get_parser(self, prog_name):
        parser = super(PowerBaremetal, self).get_parser(prog_name)

        parser.add_argument(
            'node',
            metavar='<node>',
            help="Name of UUID of the node."
        )
        on_off_group = parser.add_mutually_exclusive_group()
        on_off_group.add_argument(
            '--on',
            action='store_true',
            help='Turn baremetal node on',
        )
        on_off_group.add_argument(
            '--off',
            action='store_true',
            help='Turn baremetal node off',
        )

        return parser

    def take_action(self, parsed_args):
        self.log.debug("take_action(%s)", parsed_args)

        baremetal_client = self.app.client_manager.baremetal

        if not parsed_args.on and not parsed_args.off:
            return

        power_state = 'off' if parsed_args.off else 'on'

        baremetal_client.node.set_power_state(
            parsed_args.node, power_state)
