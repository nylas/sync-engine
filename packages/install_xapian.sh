# the xapian python bindings aren't an PyPI, so this is a hack to get
# around that. FYI, it takes a ton of time to compile.
apt-get install zlib1g-dev
apt-get install g++

export VENV=$VIRTUAL_ENV
echo $VENV
mkdir $VENV/packages && cd $VENV/packages

curl -O http://oligarchy.co.uk/xapian/1.2.15/xapian-core-1.2.15.tar.gz
curl -O http://oligarchy.co.uk/xapian/1.2.15/xapian-bindings-1.2.15.tar.gz

tar xzvf xapian-core-1.2.15.tar.gz
tar xzvf xapian-bindings-1.2.15.tar.gz

cd $VENV/packages/xapian-core-1.2.15
./configure --prefix=$VENV && make && make install

export LD_LIBRARY_PATH=$VENV/lib

cd $VENV/packages/xapian-bindings-1.2.15
./configure --prefix=$VENV --with-python && make && make install

python -c "import xapian" 
