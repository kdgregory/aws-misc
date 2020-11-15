# Data Catalog / Finding Stuff

## Table/schema lookups

Lookup by schema:

```
select  ti.schema, ti.table, ti.diststyle, ti.sortkey1, ti.tbl_rows 
from    SVV_TABLE_INFO ti 
where   ti.schema like 'X'
order   by 1, 2;
```

Lookup by table:

```
select  ti.schema, ti.table, ti.diststyle, ti.sortkey1, ti.tbl_rows 
from    SVV_TABLE_INFO ti 
where   ti.table like 'X'
order   by 1, 2;
```

Lookup by user:

```
select  ti.schema, ti.table, ti.diststyle, ti.sortkey1, ti.tbl_rows 
from    PG_USER pgu
join    PG_NAMESPACE pgn on pgn.nspowner = pgu.usesysid
join    SVV_TABLE_INFO ti on ti.schema = pgn.nspname
where   pgu.usename like 'X'
order   by 1, 2;
```


## List of tables and columns, with distribution and sort keys

This is an alternative to `PG_TABLE_DEF`, which is limited to the current search path,
and `SVV_TABLE_INFO`, which shows a "user friendly" distribution key and only the first
column of the sort key.

Variant 1: useful for a CTE.

```
select  pgn.nspname as schema_name,
        pgc.relname as table_name,
        pga.attname as column_name,
        pga.attnum  as column_order,
        pga.attisdistkey as is_distkey,
        pga.attsortkeyord as sortkey_order
from    pg_attribute pga
join    pg_class pgc on pgc.oid = pga.attrelid
join    pg_namespace pgn on pgn.oid = pgc.relnamespace
where   pgc.relkind = 'r'
and     pga.attnum > 0
```

Variant 2: for when you know the schema and/or table name.

```
select  pgn.nspname as schema_name,
        pgc.relname as table_name,
        pga.attname as column_name,
        pga.attisdistkey as is_distkey,
        pga.attsortkeyord as sortkey_order
from    pg_attribute pga
join    pg_class pgc on pgc.oid = pga.attrelid
join    pg_namespace pgn on pgn.oid = pgc.relnamespace
where   pgc.relkind = 'r'
and     pga.attnum > 0
and     schema_name like 'X'
and     table_name like 'X'
order   by pgn.nspname, pgc.relname, pga.attnum
```

## External tables

```
select  schemaname, tablename, columnname, external_type, is_nullable
from    SVV_EXTERNAL_COLUMNS
where   schemaname like 'X'
and     tablename like 'X'
order by schemaname, tablename, columnnum;
```


## Dependencies of a view

```
select  *
from    information_schema.view_table_usage
where   view_name like '%SOMETHING%';
```

```
select  *
from    information_schema.view_table_usage
where   table_name like '%SOMETHING%';
```


# Queries and Tuning

## Failed queries since a given date/time

```
select  starttime, userid, substring(querytxt, 1, 120)
from    stl_query
where   aborted = 1
and     starttime > '2015-07-10 18:00:00'
order by starttime;
Queries that use > 10Gb per slice or run for > 1 minute
select  qr.query,
        max(u.usename) as username,
        min(qr.start_time) as start_time, max(qr.end_time) as end_time,
        max(datediff(second, qr.start_time, qr.end_time)) as elapsed_time,
        sum(qr.rows) as rows,
        sum(qr.bytes) as bytes
from    SVL_QUERY_REPORT qr,
        PG_USER u
where   qr.start_time > '2016-05-19 00:00:00'
and     qr.is_diskbased = 't'
and     (qr.bytes > 10000000000 or qr.elapsed_time > 60000000)
and     u.usesysid = qr.userid
group by qr.query
order by sum(qr.bytes) desc;
```


## Longest-running queries in past 24 hours

```
select  q.query, trim(u.usename) as user, q.starttime, q.endtime,
        datediff(seconds, q.starttime, q.endtime) as elapsed,
        substring(q.querytxt, 1, 96)
from    stl_query q
join    pg_user u on u.usesysid = q.userid
where   q.starttime > dateadd(day, -1, sysdate)
order by elapsed desc
limit 20;
```

## Longest running queries by user, last hour

Note that this excludes fetches, which are largely dependent on client and network.

```
with    recent_queries(query_id,username,starttime,endtime,elapsed,querytxt) as
        (
        select  q.query, 
                trim(u.usename) as user, 
                q.starttime, 
                q.endtime,
                datediff(millisecond, q.starttime, q.endtime) as elapsed,
                q.querytxt
        from    stl_query q
        join    pg_user u on u.usesysid = q.userid
        where   q.endtime > dateadd(minute, -60, sysdate)
        and     q.querytxt not like 'fetch%'
        )
select  query_id, username, starttime, endtime, elapsed, substring(querytxt, 1, 96)
from    recent_queries
where   (username, elapsed) in
        (
        select  username, max(elapsed)
        from    recent_queries
        group   by 1
        order   by 2 desc
        )
order   by username;


## Historical query plans

```
select  parentid, nodeid, trim(plannode)
from    STL_EXPLAIN
where   query = X
order by parentid, nodeid;
```


# Disk Usage

## Space used, by schema

```
select  trim(pgn.nspname) as schema,
        sum(bl.mbytes) as mbytes
from    (
        select  db_id, id, name, 
                sum(rows) as rows
        from    STV_TBL_PERM
        group by db_id, id, name
        ) as tbl
join    PG_CLASS as pgc on pgc.oid = tbl.id
join    PG_NAMESPACE as pgn on pgn.oid = pgc.relnamespace
join    PG_DATABASE as pgdb on pgdb.oid = tbl.db_id
join    (
        select  tbl, count(*) as mbytes
        from    stv_blocklist
        group by tbl
        ) bl on bl.tbl = tbl.id
group by schema
order by mbytes desc;
```

## Top 20 tables by size

```
select  trim(pgn.nspname) as schema,
        trim(tbl.name) as name,
        sum(bl.mbytes) as mbytes
from    (
        select  db_id, id, name, 
                sum(rows) as rows
        from    STV_TBL_PERM
        group by db_id, id, name
        ) as tbl
join    PG_CLASS as pgc on pgc.oid = tbl.id
join    PG_NAMESPACE as pgn on pgn.oid = pgc.relnamespace
join    PG_DATABASE as pgdb on pgdb.oid = tbl.db_id
join    (
        select  tbl, count(*) as mbytes
        from    stv_blocklist
        group by tbl
        ) bl on bl.tbl = tbl.id
group by schema, name
order by mbytes desc
limit 20;
```


# Misc

## Identify user

```
select  *
from    pg_user
where   usesysid = X;
```

## Count of sessions by user since given time

```
select  trim(user_name) as user, count(*), min(starttime), max(endtime)
from    stl_sessions
where   starttime > trunc(sysdate)
group by trim(user_name)
order by count(*) desc;
```

```
select  trim(user_name) as user, count(*), min(starttime), max(endtime)
from    stl_sessions
where   starttime between '2015-12-16 00:00:00' and '2015-12-16 12:00:00'
group by trim(user_name)
order by count(*) desc;
```
