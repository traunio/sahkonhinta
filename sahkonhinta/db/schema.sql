drop table if exists elspot;

create table elspot (
  datetime TEXT primary key,
  price REAL
);

drop table if exists user_info;

create table user_info (
  id TEXT primary key,
  loads INTEGER,
  average REAL,
  shows INTEGER     
);
