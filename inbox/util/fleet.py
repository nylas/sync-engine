from boto import ec2
import random


def get_sync_hosts_in_zone(zone, level, include_debug=False):
    # Hack to make local dev VM work.
    if zone is None:
        return [{'name': 'localhost', 'ip_address': '127.0.0.1', 'num_procs': 4}]

    instances = []
    regions = ec2.regions()
    for region in regions:
        if not zone.startswith(region.name):
            continue
        try:
            conn = ec2.connect_to_region(region.name)
            if conn is None:
                continue

            for r in conn.get_all_instances():
                for i in r.instances:
                    if i.placement != zone:
                        continue
                    if i.tags.get('Role') != 'sync':
                        continue
                    if i.tags.get('Level') != level:
                        continue
                    if not include_debug and i.tags.get('Debug') == 'true':
                        continue
                    instances.append(i)
        except:
            print "Unable to connect to region {}".format(region.name)
            raise
    return [{
        'name': i.tags.get('Name'),
        'ip_address': i.private_ip_address,
        'num_procs': num_vcpus(i.instance_type) * 2,
        'debug': i.tags.get('Debug') == 'true',
    } for i in instances]


def get_random_sync_host(level):
    instances = []

    if level not in ('staging', 'prod'):
        return None

    regions = ec2.regions()
    for region in regions:
        try:
            conn = ec2.connect_to_region(region.name)

            for reservation in conn.get_all_instances():
                for instance in reservation.instances:
                    instances.append(instance)

            instances = filter(lambda instance: instance.state == "running", instances)
            instances = filter(lambda instance: instance.tags.get('Role') == "sync", instances)
            instances = filter(lambda instance: instance.tags.get('Level') == level, instances)
            instances = filter(lambda instance: instance.tags.get('Debug') == 'false' , instances)

        except:
            print "Unable to connect to region {}".format(region.name)
            raise

    instance = random.choice(instances)
    return instance.tags.get('Name')


# For whatever reason, the ec2 API doesn't provide us with an easy way to get
# the CPU count :-(
# These numbers were grabbed from https://aws.amazon.com/ec2/instance-types/
def num_vcpus(instance_type):
    return {
        't2.nano': 1,
        't2.micro': 1,
        't2.small': 1,
        't2.medium': 2,
        't2.large': 2,
        'm3.medium': 1,
        'm3.large': 2,
        'm3.xlarge': 4,
        'm3.2xlarge': 8,
        'm4.large': 2,
        'm4.xlarge': 4,
        'm4.2xlarge': 8,
        'm4.4xlarge': 16,
        'm4.10xlarge': 40,
        'm4.16xlarge': 64,
    }[instance_type]
