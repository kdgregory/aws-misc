# Data Catalog / Finding Stuff

## Table Lookups via `SVV_TABLE_INFO`

Note: all of these use `SVV_TABLE_INFO`, which only contains rows for tables
that have data (it joins to the blocklist).

By schema:

```
select  ti.schema, ti.table, ti.diststyle, ti.sortkey1, ti.tbl_rows 
from    SVV_TABLE_INFO ti 
where   ti.schema like 'X'
order   by 1, 2;
```

By table:

```
select  ti.schema, ti.table, ti.diststyle, ti.sortkey1, ti.tbl_rows 
from    SVV_TABLE_INFO ti 
where   ti.table like 'X'
order   by 1, 2;
```

By user:

```
select  ti.schema, ti.table, ti.diststyle, ti.sortkey1, ti.tbl_rows 
from    PG_USER pgu
join    PG_NAMESPACE pgn on pgn.nspowner = pgu.usesysid
join    SVV_TABLE_INFO ti on ti.schema = pgn.nspname
where   trim(pgu.usename) like 'X'
order   by 1, 2;
```

## Table/View Lookups via Information Schema

Add predicate on `table_type` to differentiate between tables (`and table_type = 'BASE TABLE'`)
and views (`and table_type = 'VIEW'`).

```
select  table_schema as schema_name,
        table_name,
        table_type
from    information_schema.tables
where   table_schema not in ('information_schema', 'pg_catalog')
and     table_name like 'X'
order by schema_name, table_name;
```


## External Schema Lookups

Tables by name:

```
select  schemaname, tablename, tabletype, location
from    SVV_EXTERNAL_TABLES
where   tablename like 'X'
order by schemaname, tablename;
```

Columns by table:

```
select  schemaname, tablename, columnname, external_type, is_nullable
from    SVV_EXTERNAL_COLUMNS
where   schemaname = 'X'
and     tablename = 'X'
order by schemaname, tablename, columnnum;
```


## Dependencies of a view

```
select  *
from    information_schema.view_table_usage
where   view_name like '%X%';
```

```
select  *
from    information_schema.view_table_usage
where   table_name like '%X%';
```


## List of tables and columns, with distribution and sort keys

This is an alternative to `PG_TABLE_DEF`, which is limited to the current search path,
and `SVV_TABLE_INFO`, which shows a "user friendly" distribution key and only the first
column of the sort key.

```
with    table_info (owner, schema_name, table_name, column_name, column_order, is_distkey, sortkey_order) as
(
select  pgu.usename,
        pgn.nspname,
        pgc.relname,
        pga.attname,
        pga.attnum,
        pga.attisdistkey,
        pga.attsortkeyord
from    PG_ATTRIBUTE pga
join    PG_CLASS pgc on pgc.oid = pga.attrelid
join    PG_NAMESPACE pgn on pgn.oid = pgc.relnamespace
join    PG_USER pgu on pgu.usesysid = pgn.nspowner
where   pgc.relkind = 'r'
and     pga.attnum > 0
)
```

```
select  *
from    table_info
where   schema_name like 'X'
and     table_name like 'X'
order   by schema_name, table_name, column_order;
```


# Queries and Tuning

## Failed queries since a given date/time

```
select  starttime, userid, substring(querytxt, 1, 120)
from    STL_QUERY
where   aborted = 1
and     starttime > '2015-07-10 18:00:00'
order by starttime;
```


## Queries that use > 10Gb per slice or run for > 1 minute

```
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
from    STL_QUERY q
join    PG_USER u on u.usesysid = q.userid
where   q.starttime > dateadd(day, -1, sysdate)
order by elapsed desc
limit 20;
```

## Longest running queries by user, last hour

Note that this excludes fetches, which are largely dependent on client and network
(and often indicate a query wrapped in a cursor; see below).

```
with    recent_queries(query_id,username,starttime,endtime,elapsed,querytxt) as
        (
        select  q.query, 
                trim(u.usename) as user, 
                q.starttime, 
                q.endtime,
                datediff(millisecond, q.starttime, q.endtime) as elapsed,
                q.querytxt
        from    STL_QUERY q
        join    PG_USER u on u.usesysid = q.userid
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
```


## Queries with utility text

Cursor definitions are not included in `STL_QUERY`; it simply reports fetches from that
cursor. To get the definition, you have to join to `STL_UTILITYTEXT`. This latter table
is keyed by transaction ID and statement start time, not query ID. It also splits the
text over multiple rows, which must be separately aggregated by statement and then by
transaction.

Version 1: expensive queries in past hour:

```
with
RAW_UTILITY_TEXT (xid, starttime, command) as
        (
        select  xid,
                starttime,
                trim(listagg(text) within group (order by sequence))
        from    STL_UTILITYTEXT
        group   by xid, starttime
        ),
COOKED_UTILITY_TEXT (xid, commands) as
        (
        select  xid,
                listagg(command, '\n') within group (order by starttime) as utilitytxt
        from    RAW_UTILITY_TEXT
        group   by xid
        )
select  q.query as query_id,
        q.xid as xid,
        trim(u.usename) as username,
        q.starttime as starttime,
        q.endtime as endtime,
        datediff(second, q.starttime, q.endtime) elapsed,
        substring(q.querytxt, 1, 48) as query_text,
        substring(t.commands, 1, 48) as commands
from    STL_QUERY q
join    PG_USER u on u.usesysid = q.userid
left join COOKED_UTILITY_TEXT t on t.xid = q.xid
where   q.starttime > dateadd(minute, -60, sysdate)
and     elapsed > 10
order  by query_id, xid;
```

Version 2: detail (for when you know the query ID):

```
with
RAW_UTILITY_TEXT (xid, starttime, command) as
        (
        select  xid,
                starttime,
                trim(listagg(text) within group (order by sequence))
        from    STL_UTILITYTEXT
        group   by xid, starttime
        )
select  q.xid as xid,
        t.starttime,
        trim(t.command)
from    STL_QUERY q
left join RAW_UTILITY_TEXT t on t.xid = q.xid
where   q.query = X
order   by t.starttime;
```

## In-flight queries

```
select starttime, userid, query, suspended, text from STV_INFLIGHT order by 1;
```


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
from    PG_USER
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
