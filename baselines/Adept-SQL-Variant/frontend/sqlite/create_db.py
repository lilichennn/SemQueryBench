import os
if os.path.exists('students.db'):
    os.remove('students.db')

import sqlite3

conn = sqlite3.connect('students.db')
c = conn.cursor()

# Create table : students
c.execute("""
CREATE TABLE students (
        id      integer primary key autoincrement not null,
        name        text,
        age         integer,
        gender      text,
        nationality text,
        grade       integer,
        class       integer,
        teacher_id  integer,
        phone       text,
        email       text    )
""")
conn.commit()

sql = "insert into students (name,age,gender,nationality,grade,class,teacher_id,phone,email) values(?, ?, ?, ?, ?, ?, ?, ?, ?);"
data = [
('Alice',20,'M','China',1,1,1,'010-9876-5432','Alice@gmail.com'),
('Bob',21,'M','China',1,1,1,'010-9876-5432','Bob@gmail.com'),
('Carol',22,'F','China',1,2,1,'010-9876-5432','Carol@gmail.com'),
('Dave',23,'M','UK',1,2,2,'010-9876-5432','Dave@gmail.com'),
('Eve',24,'F','UK',2,1,2,'010-9876-5432','Eve@gmail.com'),
('Frank',25,'M','UK',2,1,2,'010-9876-5432','Frank@gmail.com'),
('Grace',26,'F','USA',2,2,3,'010-9876-5432','Grace@gmail.com'),
('Harry',27,'M','USA',2,2,3,'010-9876-5432','Harry@gmail.com')
]
c.executemany(sql, data)
conn.commit()

# create table : teachers
c.execute("""
CREATE TABLE teachers (
        id      integer primary key autoincrement not null,
        name        text,
        age         integer,
        gender      text,
        nationality text,
        subject     text,
        phone       text,
        email       text    )
""")
conn.commit()
sql = "insert into teachers (name,age,gender,nationality,subject,phone,email) values(?, ?, ?, ?, ?, ?, ?);"
data = [
('TeacherA',30,'M','China','Math','010-9876-5432','TeacherA@gmail.com'),
('TeacherB',31,'F','China','English','010-9876-5432','TeacherB@gmail.com'),
('TeacherC',32,'M','UK','Science','010-9876-5432','TeacherC@gmail.com')
]
c.executemany(sql, data)
conn.commit()


# create table : grades
c.execute("""
CREATE TABLE grades (
        student_id  integer,
        subject     text,
        score       integer,
        score_date  datetime )
""")
conn.commit()
sql = "insert into grades (student_id,subject,score,score_date ) values(?, ?, ?,?);"
data = [
(1,'Math',91,'2022-01-01'),
(1,'Math',94,'2022-07-01'),
(1,'Math',92,'2023-01-01'),
(1,'Math',86,'2023-07-01'),
(1,'Math',71,'2024-01-01'),
(1,'Math',86,'2024-07-01'),
(1,'English',82,'2022-01-01'),
(1,'Science',75,'2022-01-01'),
(2,'Math',81,'2022-01-01'),
(2,'English',57,'2022-01-01'),
(2,'Science',45,'2022-01-01'),
(3,'Math',78,'2022-01-01'),
(3,'English',58,'2022-01-01'),
(3,'Science',65,'2022-01-01'),
(4,'Math',90,'2022-01-01'),
(4,'English',72,'2022-01-01'),
(4,'Science',85,'2022-01-01'),
(5,'Math',61,'2022-01-01'),
(5,'English',48,'2022-01-01'),
(5,'Science',55,'2022-01-01'),
(6,'Math',78,'2022-01-01'),
(6,'English',58,'2022-01-01'),
(6,'Science',65,'2022-01-01'),
(7,'Math',90,'2022-01-01'),
(7,'English',72,'2022-01-01'),
(7,'Science',85,'2022-01-01'),
(8,'Math',61,'2022-01-01'),
(8,'English',48,'2022-01-01'),
(8,'Science',55,'2022-01-01')
]
c.executemany(sql, data)
conn.commit()

# create table : subjects
c.execute("""
CREATE TABLE subjects (
        id      integer primary key autoincrement not null,
        name        text,
        teacher_id  integer,
        day_of_week varchar(10),
        start_time  datetime,
        end_time    datetime,
        class_room   integer
        )
""")
conn.commit()

sql = "insert into subjects (name,teacher_id,day_of_week,start_time,end_time,class_room) values(?, ?, ?,?, ?, ?);"
data = [
('Math',1,'Monday','09:00:00','10:00:00',101),
('English',2,'Tuesday','10:00:00','11:00:00',102),
('Science',3,'Wednesday','11:00:00','12:00:00',101)
]
c.executemany(sql, data)
conn.commit()

c.close()




