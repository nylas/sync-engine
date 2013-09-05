import time
import os

from fabric.api import env, sudo, run, put, cd
from fabric.exceptions import NetworkError
import boto
import boto.ec2
from boto.route53.record import ResourceRecordSets



aws_key = 'XXXXXXXXXXXXXXXXXXXXXXXX'
aws_secret = 'XXXXXXXXXXXXXXXXXXXXXXXX'
aws_key_path = '/path/to/key/pair'
aws_key_pair = 'keypairname'


aws_security_group = 'quick-start-1'  # opens 22, 80, 3306

# Here lie the Amazon secrets
AWS = {
            'secrets' : {
                'aws_key' : aws_key,
                'aws_secret': aws_secret,
                'aws_key_path': aws_key_path,
            },
            'defaults' : {
                    'image_id' : 'ami-70f96e40',  #  Ubuntu Cloud Guest AMI ID ami-70f96e40 (x86_64)
                    # 'image_id' : 'ami-2231bf12',       # Amazon Linux AMI i386 EBS
                    'instance_type' : 't1.micro',      # Micro Instance
                    'security_groups': [aws_security_group],
                    'key_name': aws_key_pair,
            }
}


region = 'us-west-2'  # Oregon
env.key_filename = AWS['secrets']['aws_key_path']
# env.forward_agent = True
env.user = "ubuntu"


def deploy_server():
    instance = create_instance()
    print 'Waiting for instance to boot.'
    time.sleep(60)
    env.host_string = "ubuntu@%s" % instance.public_dns_name
    print 'connecting to:', env.host_string
    # Install Web
    connect_attempts = 0
    while connect_attempts <= 10:
        try:
            install_web()
            break
        except NetworkError, e:
            print e
            print "Failed to connect: used attempt %s of 10" % \
                                            (connect_attempts)
            connect_attempts += 1
            time.sleep(10)
        except Exception, e:
            print "Failed to install_web"
            break


def create_instance():

    SERVER = {
            'image_id' : AWS['defaults']['image_id'],
            'instance_type' : AWS['defaults']['instance_type'],
            'security_groups' : AWS['defaults']['security_groups'],
            'key_name' : AWS['defaults']['key_name'],
    }

    conn = boto.ec2.connect_to_region(region,
                            aws_access_key_id=AWS['secrets']['aws_key'],
                            aws_secret_access_key=AWS['secrets']['aws_secret'])

    print 'Creating server with config:', SERVER
    reservation = conn.run_instances( **SERVER)
    print reservation
    instance = reservation.instances[0]
    time.sleep(10)
    while instance.state != 'running':
        time.sleep(5)
        instance.update()
        print "Instance state: %s" % (instance.state)

    # 'public_dns_name': u'ec2-54-200-2-231.us-west-2.compute.amazonaws.com', 'ip_address': u'54.200.2.231'
    return instance




remote_dir = '/home/ubuntu/'
remote_code_dir = os.path.join(remote_dir, 'code')

def install_web():

    # Basic
    install_pip_and_virtualenv()
    install_inbox_src('git@github.com:inboxapp/inbox.git')
    copy_ssl_keys()

    install_nginx()
    install_mysql('hunter2')  # LOL
    server_domain_name = create_dns_record()
    start_webserver()

    print "Success provisioning and configuring dev server!"
    print "Go visit it at %s" % str(server_domain_name)

    # Note: This doesn't yet clean up domain names after termination, so
    # please remember to do that.
    # We also need to somehow reassociate a machine with it's CNAME record
    # after restarts, since the Amazon external DNS will change.



def pre_install():
    sudo('apt-get update -y')


def install_mysql(master_password):
    sudo("debconf-set-selections <<< 'mysql-server-<version> mysql-server/root_password password %s'" % master_password)
    sudo("debconf-set-selections <<< 'mysql-server-<version> mysql-server/root_password_again password %s'" % master_password)
    sudo('apt-get install -y \
            mysql-server \
            mysql-client')

    # Create default DB
    database_name = 'inbox-db'
    run('mysqladmin -u root --password=%s create %s' % (master_password, database_name) )

    config_data = """
MYSQL_USER = root
MYSQL_PASSWORD = %s
MYSQL_HOSTNAME = 127.0.0.1
MYSQL_PORT = 3306
MYSQL_DATABASE = %s
""" % (master_password, database_name)

    sudo(""" echo '%s' >> %s/local-config.cfg """ % (config_data, remote_code_dir) , pty=False)

    # /usr/bin/mysqladmin -u root password 'new-password'
    # /usr/bin/mysqladmin -u root -h hostname password 'new-password'


def install_pip_and_virtualenv():
    sudo('apt-get -y update')
    sudo('apt-get install -y python-pip python-dev build-essential libmysqlclient-dev')  # python-dev for gevent
    sudo('pip install --upgrade pip')
    sudo('pip install distribute==0.6.28')  # For MySQL-python
    sudo('pip install --upgrade virtualenv')


def install_inbox_src(git_src_repo):
    sudo('virtualenv venv')
    sudo('. venv/bin/activate')

    sudo('apt-get install -y git gcc python-gevent')  # For some requirements

    put('../requirements.txt', remote_dir)
    sudo('pip install -r %s/requirements.txt' % (remote_dir))
    # Checkout Code from GitHub
    github_fingerprint = "github.com,207.97.227.239 ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAq2A7hRGmdnm9tUDbO9IDSwBK6TbQa+PXYPCPy6rbTrTtw7PHkccKrpp0yVhp5HdEIcKr6pLlVDBfOLX9QUsyCOV0wzfjIJNlGEYsdlLJizHhbn2mUjvSAHQqZETYP81eFzLQNnPHt4EVVUh7VfDESU84KezmD5QlWpXLmvU31/yMf+Se8xhHTvKSCZIFImWwoG6mbUoWf9nzpIoaSjB+weqqUUmpaaasXVal72J+UX2B+2RPW3RcT0eOzQgqlJL3RKrTJvdsjE3JEAvGq3lGHSZXy28G3skua2SmVi/w4yCE6gbODqnTWlg7+wC604ydGXA8VJiS5ap43JXiUFFAaQ=="

    sudo(""" echo '%s' >> .ssh/known_hosts """ % github_fingerprint , pty=True)
    put("ssh-config", ".ssh/config", mode=0600)
    put('keys/server_deploy_private.key', '.ssh/', mode=0600)
    run('git clone %s %s' % (git_src_repo, remote_code_dir))

    config_data = """[development]
"""
    sudo(""" echo '%s' >> %s/local-config.cfg """ % (config_data, remote_code_dir) , pty=False)


def update_code():
    with cd(remote_code_dir):
        run('git pull origin master')

def install_nginx():
    sudo('apt-get -y update')
    sudo('apt-get -y install python-software-properties -y')
    sudo('add-apt-repository ppa:nginx/stable -y')
    sudo('apt-get -y update')
    sudo('apt-get -y install nginx')
    put('nginx.conf', '/etc/nginx/nginx.conf', use_sudo=True)
    put('nginx-mime.types', '/etc/nginx/mime.types', use_sudo=True)


def copy_ssl_keys():
    sudo('mkdir -p /etc/nginx/certs')
    put('../certs/inboxapp-combined.crt', '/etc/nginx/certs/', use_sudo=True)
    put('../certs/server.key', '/etc/nginx/certs/', use_sudo=True)


def create_dns_record():
    route53_conn = boto.connect_route53(AWS['secrets']['aws_key'],
                            AWS['secrets']['aws_secret'])

    inbox_zone_id = 'Z2UWV7M060PW37'  # XXXX.inboxapp.com record zone

    server_domain_name = None
    taken_domain_names = [rset.name for rset in route53_conn.get_all_rrsets(inbox_zone_id)]
    for i in range(100):
        t = "dev-%02d.inboxapp.com." % i
        if t not in taken_domain_names:
            server_domain_name = t
            break

    if not server_domain_name:
        print 'You are out of development DNS records! Go make more or delete some'

    print "%s is available." % server_domain_name

    changes = ResourceRecordSets(connection=route53_conn, hosted_zone_id=inbox_zone_id)

    # change = changes.add_change("DELETE", "dev-01.inboxapp.com", "CNAME")
    change = changes.add_change("CREATE", server_domain_name, "CNAME", ttl=60)

    change.add_value(get_public_hostname())
    changes.commit()
    print "Committed change to Amazon Route 53. This typically takes a minute to update."

    if server_domain_name.endswith('.'):
        server_domain_name = server_domain_name[:-1]

    config_data = """
SERVER_DOMAIN_NAME      =       %s
"""  % server_domain_name
    sudo(""" echo '%s' >> %s/local-config.cfg """ % (config_data, remote_code_dir) , pty=False)

    return server_domain_name


def get_public_hostname():
    return run('curl http://169.254.169.254/latest/meta-data/public-hostname 2>/dev/null')

def get_public_ip():
    return run('curl http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null')

def get_private_ip():
    return run('curl http://169.254.169.254/latest/meta-data/local-ipv4 2>/dev/null')


def start_webserver():
    with cd(remote_dir):
        # sudo unlink /tmp/supervisor.sock
        put('supervisord.conf', remote_dir)
        sudo('supervisord -c supervisord.conf')
        # run('nohup ./inbox start >& ./app_log.log < /dev/null', pty=False)
        sudo('service nginx restart -p ./code')


# Elastic IPs unused for now. We can do this with the main production server.
# def associate_elastic_ip(instance_id):
#     conn = boto.ec2.connect_to_region(region,
#                             aws_access_key_id=AWS['secrets']['aws_key'],
#                             aws_secret_access_key=AWS['secrets']['aws_secret'])
#     new_address = conn.allocate_address()
#     conn.associate_address(instance_id, new_address.public_ip)
#     # conn.release_address(new_address.public_ip)
#     # addrs = conn.get_all_addresses()
#     # for a in addrs:
#     #     print a.public_ip
#     route53 = Route53Connection(AWS['secrets']['aws_key'],
#                             AWS['secrets']['aws_secret'])


# Simple Fab Functions
##########################
def host_type():
    run('uname -a')

def free_space():
    run('df -h')

def what_is_my_name():
    run('whoami')

def what_is_sudos_name():
    sudo('whoami')

