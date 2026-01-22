# exjobb_cooperation
```
COPY (
  SELECT pid, note_cooperation
  FROM note_cooperation
  WHERE note_cooperation IS NOT NULL
) TO 'note_cooperation.csv'
WITH (HEADER, DELIMITER ',');
```

Running coop_inventory.py   
Input file: note_cooperation.csv  
```
pid,note_cooperation
1138389,"{'pid': 1138389, 'org_coop': Skanska Sverige AB}"
550267,"{'pid': 550267, 'org_coop': ABB LV Motors,Åke Andersson}"
693749,"{'pid': 693749, 'org_coop': Stoneridge Electronics}"
724369,"{'pid': 724369, 'org_coop': Mostphotos}"
743805,"{'pid': 743805, 'org_coop': Ute's group, MTC, Karolinska Institute}"
542132,"{'pid': 542132, 'org_coop': Tobii Technology AB}"
706730,"{'pid': 706730, 'org_coop': DGC One AB}"
1230122,"{'pid': 1230122, 'org_coop': KRY}"
1252231,"{'pid': 1252231, 'org_coop': H&E Solutions}"
```
Output file: institution_inventory_raw.json
```
```

