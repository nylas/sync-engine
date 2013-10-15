drop table if exists foldermeta;
drop table if exists blockmeta;
drop table if exists collections;
drop table if exists messagemeta;
drop table if exists uidvalidity;
drop table if exists rawmessage;
update user set initial_sync_done = 0;
# should really clear all namespaces that aren't root namespaces too
