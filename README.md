SET PAGESIZE 0;
SET FEEDBACK OFF;
SET HEADING OFF;
SPOOL create_tablespaces.sql;

SELECT 'CREATE TABLEQSPACE ' || dt.tablespace_name ||
       ' DATAFILE ''' || df.file_name || ''' SIZE ' ||
       TO_CHAR(df.bytes/1024/1024) || 'M ' ||
       DECODE(df.autoextensible, 'YES', 'AUTOEXTEND ON NEXT ' ||
       TO_CHAR(df.increment_by * df.block_size/1024/1024) || 'M MAXSIZE ' ||
       DECODE(df.maxbytes, 0, 'UNLIMITED', TO_CHAR(df.maxbytes/1024/1024) || 'M'), 'AUTOEXTEND OFF') ||
       ' ' || DECODE(dt.logging, 'LOGGING', 'LOGGING', 'NOLOGGING') || ';'
FROM dba_tablespaces dt, dba_data_files df
WHERE dt.tablespace_name = df.tablespace_name;

SPOOL OFF;
