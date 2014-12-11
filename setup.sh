#!/bin/bash

set -e

prod=false
while getopts "p" opt; do
    case $opt in
        p)
            prod=true
            ;;
    esac
done

color() {
      printf '\033[%sm%s\033[m\n' "$@"
      # usage color "31;5" "string"
      # 0 default
      # 5 blink, 1 strong, 4 underlined
      # fg: 31 red,  32 green, 33 yellow, 34 blue, 35 purple, 36 cyan, 37 white
      # bg: 40 black, 41 red, 44 blue, 45 purple
      }

color '36;1' "
      _____       _
     |_   _|     | |
       | |  _ __ | |__   _____  __
       | | | '_ \| '_ \ / _ \ \/ /
      _| |_| | | | |_) | (_) >  <
     |_____|_| |_|_.__/ \___/_/\_\\

     This script installs dependencies for Inbox.

     For more details, visit:
     https://www.github.com/inboxapp/inbox
"

if ! [ -e ./setup.py ] || ! [ -e ./setup.sh ] ; then
    color '31;1' "Error: setup.sh should be run from the inbox repo" >&2
    exit 1
fi

color '35;1' 'Updating packages...'
apt-get update
apt-get -y install python-software-properties

# Preconfigure MySQL root password
echo "mysql-server mysql-server/root_password password root" | debconf-set-selections
echo "mysql-server mysql-server/root_password_again password root" | debconf-set-selections

color '35;1' 'Installing dependencies from apt-get...'
apt-get -y install git \
                   wget \
                   supervisor \
                   mysql-server \
                   mysql-client \
                   python \
                   python-dev \
                   python-pip \
                   python-setuptools \
                   build-essential \
                   libmysqlclient-dev \
                   gcc \
                   g++ \
                   libzmq-dev \
                   libxml2-dev \
                   libxslt-dev \
                   lib32z1-dev \
                   libffi-dev \
                   pkg-config \
                   python-lxml \
                   tmux \
                   curl \
                   tnef \
                   stow \

# Switch to a temporary directory to install dependencies, since the source
# directory might be mounted from a VM host with weird permissions.
src_dir=$(pwd)
temp_dir=`mktemp -d`
cd "$temp_dir"

# Workaround for "error: sodium.h: No such file or directory" bug
# https://github.com/pyca/pynacl/issues/79
libsodium_ver=1.0.0
color '35;1' 'Ensuring libsodium version...'
if ! pkg-config --atleast-version="${libsodium_ver}" libsodium; then
    # Ubuntu precise doesn't have a libsodium-dev package, so we build it
    # ourselves and install it to /usr/local (using GNU stow so that we can
    # uninstall it later).

    # Uninstall old version
    if pkg-config --exists libsodium; then
        libsodium_oldver=`pkg-config --modversion libsodium`
        color '35;1' " > Uninstalling libsodium-${libsodium_oldver}..."
        stow -d /usr/local/stow -D "libsodium-${libsodium_oldver}"
        ldconfig
        if pkg-config --exists libsodium; then
            color '31;1' " > Unable to uninstall libsodium-${libsodium_oldver}"
            exit 1
        fi
    fi

    color '35;1' " > Downloading and installing libsodium-${libsodium_ver}..."
    curl -L -O https://github.com/jedisct1/libsodium/releases/download/${libsodium_ver}/libsodium-${libsodium_ver}.tar.gz
    echo 'ced1fe3d2066953fea94f307a92f8ae41bf0643739a44309cbe43aa881dbc9a5 *libsodium-1.0.0.tar.gz' | sha256sum -c || exit 1
    tar -xzf libsodium-${libsodium_ver}.tar.gz
    cd libsodium-${libsodium_ver}
    ./configure --prefix=/usr/local/stow/libsodium-${libsodium_ver}
    make -j4
    rm -rf /usr/local/stow/libsodium-${libsodium_ver}
    mkdir -p /usr/local/stow/libsodium-${libsodium_ver}
    make install
    stow -d /usr/local/stow -R libsodium-${libsodium_ver}
    ldconfig
    cd ..
    rm -rf libsodium-${libsodium_ver} libsodium-${libsodium_ver}.tar.gz

    if pkg-config --exists libsodium; then
        color '34;1' " > libsodium-${libsodium_ver} installed."
    else
        color '31;1' " > Unable to install libsodium-${libsodium_ver}"
        exit 1
    fi
fi

if ! ${prod}; then
    color "35;1" "Ensuring redis version..."
    redis_version=2.8.17
    if ! [ -e /usr/local/stow/redis-${redis_version} ]; then
        color "35;1" "Downloading and installing redis-${redis_version}..."
        curl -L -O --progress-bar http://download.redis.io/releases/redis-${redis_version}.tar.gz
        echo "913479f9d2a283bfaadd1444e17e7bab560e5d1e *redis-${redis_version}.tar.gz" | sha1sum -c --quiet || exit 1
        tar -xf redis-${redis_version}.tar.gz
        cd redis-${redis_version}
        make -j2 || exit 1
        rm -rf /usr/local/stow/redis-${redis_version}
        make PREFIX=/usr/local/stow/redis-${redis_version} install
        stow -d /usr/local/stow/ -R redis-${redis_version}
        cd utils
        echo -e -n "\n\n\n\n\n\n" | ./install_server.sh
        rm -f /tmp/6379.conf
        cd ../..
        rm -rf redis-${redis_version} redis-${redis_version}.tar.gz
    fi
    color '34;1' 'redis-'${redis_version}' installed.'
fi

color '35;1' 'Ensuring setuptools and pip versions...'
# If python-setuptools is actually the old 'distribute' fork of setuptools,
# then the first 'pip install setuptools' will be a no-op.
pip install 'pip>=1.5.6' 'setuptools>=5.3'
hash pip        # /usr/bin/pip might now be /usr/local/bin/pip
pip install 'pip>=1.5.6' 'setuptools>=5.3'

# Install tox for running tests
pip install 'tox'

# Now that the new version of pip and our other non-pip dependencies are
# installed, we can switch back to the source directory.
cd "$src_dir"

color '35;1' 'Removing .pyc files...'   # they might be stale
find . -name \*.pyc -delete

color '35;1' 'Installing dependencies from pip...'
SODIUM_INSTALL=system pip install -r requirements.txt

pip install -e .
if [ -d "../inbox-eas" ]; then
    pip install -r ../inbox-eas/requirements.txt
    pip install -e ../inbox-eas
fi

color '35;1' 'Finished installing dependencies.'

mkdir -p /etc/inboxapp
chown $SUDO_UID:$SUDO_GID /etc/inboxapp

color '35;1' 'Copying default development configuration to /etc/inboxapp'
src=./etc/config-dev.json
dest=/etc/inboxapp/config.json
if [ ! -f $dest ]; then
    install -m0644 -o$SUDO_UID $src $dest
elif [ $src -nt $dest ]; then
    set +e
    diff_result=$(diff -q $src $dest)
    different=$?
    set -e
    if [ $different -ne 0 ]; then
        echo "Error: inbox config is newer and merging of configs not (yet) supported."
        echo "Diffs:"
        echo "src: $src dest: $dest"
        diff $dest $src
        exit 1
    fi
fi
# make sure that users upgrading from a previous release get file permissions
# right
chmod 0644 $dest
chown $SUDO_UID:$SUDO_GID $dest

color '35;1' 'Copying default secrets configuration to /etc/inboxapp'
src=./etc/secrets-dev.yml
dest=/etc/inboxapp/secrets.yml
if [ ! -f $dest ]; then
    install -m0600 -o$SUDO_UID $src $dest
elif [ $src -nt $dest ]; then
    set +e
    diff_result=$(diff -q $src $dest)
    different=$?
    set -e
    if [ $different -ne 0 ]; then
        echo "Error: inbox secrets config is newer and merging of configs not (yet) supported."
        echo "Diffs:"
        echo "src: $src dest: $dest"
        diff $dest $src
        exit 1
    fi
fi
# make sure that users upgrading from a previous release get file permissions
# right
chmod 0600 $dest
chown $SUDO_UID:$SUDO_GID $dest

if ! $prod; then
    # Mysql config
    color '35;1' 'Copying default mysql configuration to /etc/mysql/conf.d'
    src=./etc/my.cnf
    dest=/etc/mysql/conf.d/inboxapp.cnf
    if [ ! -f $dest ]; then
        install -m0644 $src $dest
    elif [ $src -nt $dest ]; then
        set +e
        diff_result=$(diff -q $src $dest)
        different=$?
        set -e
        if [ $different -ne 0 ]; then
            echo "Error: inbox config is newer and merging of configs not (yet) supported."
            echo "Diffs:"
            echo "src: $src dest: $dest"
            diff $dest $src
            exit 1
        fi
    fi

    mysqld_safe &
    sleep 10

    db_name=`cat /etc/inboxapp/config.json  | grep "MYSQL_DATABASE" | awk '{ print $2 }' | sed "s/\"\(.*\)\",/\1/"`
    if ! have_dbs=$(mysql -e "show databases like '$db_name'" | grep -q $db_name); then
        color '35;1' 'Creating databases...'
        python bin/create-db
    else
        color '35;1' 'Upgrading databases...'
        alembic upgrade head
    fi
fi

color '35;1' 'Cleaning up...'
apt-get -y purge build-essential
apt-get -y autoremove

mkdir -p /var/lib/inboxapp
chown $SUDO_UID:$SUDO_GID /var/lib/inboxapp

mkdir -p /var/log/inboxapp
chown $SUDO_UID:$SUDO_GID /var/log/inboxapp

git config branch.master.rebase true

color '35;1' 'Done!.'
