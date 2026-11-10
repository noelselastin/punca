# Introduction to Databases (DB)

## DB-WHY | Why databases
In **Introduction to Databases** (*Topic: Database fundamentals*), **Why databases** covers: Data versus information, files versus a DBMS. Prerequisites: Structured data (`FC-TABLES`). To master `DB-WHY`, focus on applying data versus information, files versus a dbms accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-MODEL | Relational model
In **Introduction to Databases** (*Topic: Database fundamentals*), **Relational model** covers: Tables, rows, columns and relations. Prerequisites: Why databases (`DB-WHY`). To master `DB-MODEL`, focus on applying tables, rows, columns and relations accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-KEYS | Keys
In **Introduction to Databases** (*Topic: Database fundamentals*), **Keys** covers: Primary, candidate and foreign keys. Prerequisites: Relational model (`DB-MODEL`). To master `DB-KEYS`, focus on applying primary, candidate and foreign keys accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-TYPES | Data types and domains
In **Introduction to Databases** (*Topic: Database fundamentals*), **Data types and domains** covers: Attribute types and allowed values. Prerequisites: Relational model (`DB-MODEL`), Data types (`PRG-TYPE`). To master `DB-TYPES`, focus on applying attribute types and allowed values accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-ER | Entity-relationship modelling
In **Introduction to Databases** (*Topic: Data modelling*), **Entity-relationship modelling** covers: Entities, attributes and relationships. Prerequisites: Keys (`DB-KEYS`). To master `DB-ER`, focus on applying entities, attributes and relationships accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-CARD | Cardinality and participation
In **Introduction to Databases** (*Topic: Data modelling*), **Cardinality and participation** covers: One-to-one, one-to-many and many-to-many. Prerequisites: Entity-relationship modelling (`DB-ER`). Related cross-links: Relations (`CM-REL`). To master `DB-CARD`, focus on applying one-to-one, one-to-many and many-to-many accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-ERD | ER diagram to tables
In **Introduction to Databases** (*Topic: Data modelling*), **ER diagram to tables** covers: Mapping entities and relationships to relational tables. Prerequisites: Cardinality and participation (`DB-CARD`), Keys (`DB-KEYS`). To master `DB-ERD`, focus on applying mapping entities and relationships to relational tables accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-INTEG | Integrity constraints
In **Introduction to Databases** (*Topic: Data modelling*), **Integrity constraints** covers: Entity and referential integrity. Prerequisites: Keys (`DB-KEYS`). To master `DB-INTEG`, focus on applying entity and referential integrity accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-ANOM | Redundancy and anomalies
In **Introduction to Databases** (*Topic: Normalisation*), **Redundancy and anomalies** covers: Insert, update and delete anomalies. Prerequisites: Relational model (`DB-MODEL`). To master `DB-ANOM`, focus on applying insert, update and delete anomalies accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-FD | Functional dependencies
In **Introduction to Databases** (*Topic: Normalisation*), **Functional dependencies** covers: Determinants and dependencies between attributes. Prerequisites: Keys (`DB-KEYS`). Related cross-links: Functions as mappings (`CM-FUNCSET`). To master `DB-FD`, focus on applying determinants and dependencies between attributes accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-1NF | First normal form
In **Introduction to Databases** (*Topic: Normalisation*), **First normal form** covers: Atomic values and no repeating groups. Prerequisites: Redundancy and anomalies (`DB-ANOM`), Keys (`DB-KEYS`). To master `DB-1NF`, focus on applying atomic values and no repeating groups accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-2NF | Second normal form
In **Introduction to Databases** (*Topic: Normalisation*), **Second normal form** covers: Removing partial dependencies. Prerequisites: First normal form (`DB-1NF`), Functional dependencies (`DB-FD`). To master `DB-2NF`, focus on applying removing partial dependencies accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-3NF | Third normal form
In **Introduction to Databases** (*Topic: Normalisation*), **Third normal form** covers: Removing transitive dependencies. Prerequisites: Second normal form (`DB-2NF`). To master `DB-3NF`, focus on applying removing transitive dependencies accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-SELECT | SELECT basics
In **Introduction to Databases** (*Topic: SQL*), **SELECT basics** covers: SELECT, FROM and WHERE. Prerequisites: Data types and domains (`DB-TYPES`), Expressions and operators (`PRG-EXPR`). Related cross-links: Propositional logic (`CM-PROP`). To master `DB-SELECT`, focus on applying select, from and where accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-FILTER | Filtering and sorting
In **Introduction to Databases** (*Topic: SQL*), **Filtering and sorting** covers: AND, OR, NOT, LIKE, IN and ORDER BY. Prerequisites: SELECT basics (`DB-SELECT`). Related cross-links: Propositional logic (`CM-PROP`). To master `DB-FILTER`, focus on applying and, or, not, like, in and order by accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-AGG | Aggregates and grouping
In **Introduction to Databases** (*Topic: SQL*), **Aggregates and grouping** covers: COUNT, SUM, AVG, GROUP BY and HAVING. Prerequisites: Filtering and sorting (`DB-FILTER`). Related cross-links: Descriptive statistics (`CM-STAT`). To master `DB-AGG`, focus on applying count, sum, avg, group by and having accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-JOIN | Joins
In **Introduction to Databases** (*Topic: SQL*), **Joins** covers: INNER, LEFT and RIGHT joins. Prerequisites: SELECT basics (`DB-SELECT`), Keys (`DB-KEYS`). Related cross-links: Sets (`CM-SETS`). To master `DB-JOIN`, focus on applying inner, left and right joins accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-SETOPS | Set operations in SQL
In **Introduction to Databases** (*Topic: SQL*), **Set operations in SQL** covers: UNION, INTERSECT and EXCEPT. Prerequisites: Filtering and sorting (`DB-FILTER`). Related cross-links: Sets (`CM-SETS`). To master `DB-SETOPS`, focus on applying union, intersect and except accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-SUBQ | Subqueries
In **Introduction to Databases** (*Topic: SQL*), **Subqueries** covers: Nested queries in WHERE and FROM. Prerequisites: Joins (`DB-JOIN`), Aggregates and grouping (`DB-AGG`). To master `DB-SUBQ`, focus on applying nested queries in where and from accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-DDL | Defining tables
In **Introduction to Databases** (*Topic: SQL*), **Defining tables** covers: CREATE TABLE, ALTER and constraints. Prerequisites: Data types and domains (`DB-TYPES`), Keys (`DB-KEYS`), Integrity constraints (`DB-INTEG`). To master `DB-DDL`, focus on applying create table, alter and constraints accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-DML | Modifying data
In **Introduction to Databases** (*Topic: SQL*), **Modifying data** covers: INSERT, UPDATE and DELETE. Prerequisites: Defining tables (`DB-DDL`), Filtering and sorting (`DB-FILTER`). To master `DB-DML`, focus on applying insert, update and delete accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-RELALG | Relational algebra
In **Introduction to Databases** (*Topic: Beyond the basics*), **Relational algebra** covers: Select, project and join as set operations. Prerequisites: Relational model (`DB-MODEL`), Sets (`CM-SETS`). To master `DB-RELALG`, focus on applying select, project and join as set operations accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-VIEW | Views and indexes
In **Introduction to Databases** (*Topic: Beyond the basics*), **Views and indexes** covers: Virtual tables and speeding up queries. Prerequisites: Joins (`DB-JOIN`), Defining tables (`DB-DDL`). To master `DB-VIEW`, focus on applying virtual tables and speeding up queries accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-TXN | Transactions and ACID
In **Introduction to Databases** (*Topic: Beyond the basics*), **Transactions and ACID** covers: Commit, rollback and the ACID properties. Prerequisites: Modifying data (`DB-DML`). To master `DB-TXN`, focus on applying commit, rollback and the acid properties accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-SEC | Security and backup
In **Introduction to Databases** (*Topic: Beyond the basics*), **Security and backup** covers: Users, privileges and backups. Prerequisites: Defining tables (`DB-DDL`). To master `DB-SEC`, focus on applying users, privileges and backups accurately on small examples first, checking each prerequisite step before moving to dependent topics.

## DB-APP | Connecting applications
In **Introduction to Databases** (*Topic: Beyond the basics*), **Connecting applications** covers: Using a database from Python or Java. Prerequisites: Modifying data (`DB-DML`), Subprograms (`PRG-FUNC`). Related cross-links: Defining and calling functions (`PY-FUNC`), Methods (`JV-METH`). To master `DB-APP`, focus on applying using a database from python or java accurately on small examples first, checking each prerequisite step before moving to dependent topics.
