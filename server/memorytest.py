import sys

sl = []
i = 0
# some magic 1024 - overhead of string object
fill_size = 1024
if sys.version.startswith('2.7'):
    fill_size = 1003
if sys.version.startswith('3'):
    fill_size = 497
print(fill_size)
MiB = 0
while True:
    s = str(i).zfill(fill_size)
    sl.append(s)
    if i == 0:
        try:
            sys.stderr.write('size of one string %d\n' % (sys.getsizeof(s)))
        except AttributeError:
            pass
    i += 1
    if i % 1024 == 0:
        MiB += 1
        if MiB % 25 == 0:
            sys.stderr.write('%d [MiB]\n' % (MiB))