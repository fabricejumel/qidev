#!/usr/bin/env python
import sys
import argparse

running = True


def main():
    try:
        import handlers as hs
    except ImportError as e:
        print('Missing Dependency: {}'.format(e))
        sys.exit()

    parser = argparse.ArgumentParser(description='qidev')
    parser.add_argument('--verbose', help='be verbose', dest='verbose',
                        action='store_true', default=False)

    subs = parser.add_subparsers(help='commands', dest='command')

    config_parser = subs.add_parser('config', help='configure defaults for qidev')
    config_parser.add_argument('field', help='the field to configure', type=str)
    config_parser.add_argument('value', help='set field to value', type=str)

    connect_parser = subs.add_parser('connect', help='shortcut to config hostname')
    connect_parser.add_argument('hostname', help='hostname of the robot', type=str)

    install_parser = subs.add_parser('install',
                                     help='package and install a project directory on a robot')
    install_parser.add_argument('path', help='path to the project directory to package ' +
                                'and install', type=str)
    remove_parser = subs.add_parser('remove',
                                    help='remove a package from a robot')

    show_parser = subs.add_parser('show', help='show the packages installed on a robot')
    mutex = show_parser.add_mutually_exclusive_group()
    mutex.add_argument('-s', '--services', help='show the services installed on the robot',
                       action='store_true', dest='s')
    mutex.add_argument('-i', '-p', '--inspect', '--package',
                       help='inspect package, prompts for package name',
                       action='store_true', dest='i')
    mutex.add_argument('-a', '--active',
                       help='show active content (behaviors and services) with realtime updates',
                       action='store_true', dest='active')

    start_parser = subs.add_parser('start',
                                   help='focus an activity with ALAutonomousLife; prompts for ' +
                                   'name on return')
    start_parser.add_argument('-b', '--bm',
                              help='use ALBehaviorManager to start a behavior or service',
                              dest='bm', action='store_true')
    stop_parser = subs.add_parser('stop',
                                  help='stop the currently focused activity; prompts for ' +
                                  'name on return')
    stop_parser.add_argument('-b', '--bm',
                             help='use ALBehaviorManager to stop a behavior or service',
                             dest='bm', action='store_true')

    life_parser = subs.add_parser('life', help='toggle ALAutonomousLife')
    life_parser.add_argument('state', help='turn ALAutonomousLife on or off', type=str)

    nao_parser = subs.add_parser('nao', help='run nao commands on remote robot')
    nao_parser.add_argument('action', help='restart, start, stop naoqi on remote host',
                            type=str)

    subs.add_parser('reboot', help='reboot the robot')
    subs.add_parser('shutdown', help='shutdown the robot')

    subs.add_parser('rest', help='put the robot to rest')
    subs.add_parser('wake', help='wake up the robot')

    volume_parser = subs.add_parser('vol', help='adjust the volume on the robot')
    volume_parser.add_argument('level',
                               help='int from 0 to 100 with optional + or - prefix to modify ' +
                               'current level; use "up" and "down" to increase or decrease ' +
                               'volume by 10.', type=str)

    dialog_parser = subs.add_parser('dialog', help='show dialog')

    log_parser = subs.add_parser('log', help='show tail-naoqi.log')

    args = parser.parse_args()
    handler = args.command + '_handler'
    if not args.verbose:
        sys.tracebacklimit = 0
    getattr(hs, handler)(args)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit()

    except RuntimeError as e:
        print(e)
        sys.exit()
