drop table if exists foldermeta;
drop table if exists messagepart;
drop table if exists collections;
drop table if exists messagemeta;
drop table if exists uidvalidity;
drop table if exists rawmessage;
update users set initial_sync_done = 0;
