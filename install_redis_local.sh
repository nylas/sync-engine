#!/bin/bash
VERSION="3.0.5"
ARCHIVE=redis-${VERSION}.tar.gz

if [ -z "${VIRTUAL_ENV}" ]; then
echo "Please activate a virtualenv first";
    exit
fi

pushd /tmp/
if [ ! -f redis-${VERSION}.tar.gz ]
   then
   wget http://download.redis.io/releases/${ARCHIVE}
fi
DIRNAME=`tar tzf ${ARCHIVE} 2>/dev/null | head -n 1`
tar xzf ${ARCHIVE}
pushd ${DIRNAME}
# make / make install w/ prefix
make PREFIX=${VIRTUAL_ENV}
make PREFIX=${VIRTUAL_ENV} install
mkdir -p ${VIRTUAL_ENV}/etc/
mkdir -p ${VIRTUAL_ENV}/run/

mkdir -p ${VIRTUAL_ENV}/etc/
mkdir -p ${VIRTUAL_ENV}/run/
sed -i 's/daemonize no/daemonize yes/' redis.conf
# prepare VIRTUAL_ENV-path for sed (escape / with  \/)
VIRTUAL_ENV_ESC="${VIRTUAL_ENV//\//\\/}"
sed -i "s/\/var\/run/${VIRTUAL_ENV_ESC}\/run/" redis.conf
sed -i "s/dir \.\//dir ${VIRTUAL_ENV_ESC}\/run\//" redis.conf
cp redis.conf ${VIRTUAL_ENV}/etc/
popd
popd
