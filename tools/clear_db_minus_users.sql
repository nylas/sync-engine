drop table if exists attachmentpart;
drop table if exists foldermeta;
drop table if exists messagepart;
drop table if exists messagemeta;
drop table if exists uidvalidity;
update users set initial_sync_done = 0;
