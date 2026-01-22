# exjobb_cooperation
```
COPY (
  SELECT pid, note_cooperation
  FROM note_cooperation
  WHERE note_cooperation IS NOT NULL
) TO 'note_cooperation.csv'
WITH (HEADER, DELIMITER ',');
```
