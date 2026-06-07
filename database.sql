create database goparky;
use goparky; 
create table users(
id int primary key,
name varchar(10) NOT NULL,
role varchar(10) NOT NULL,
contact varchar(15) NOT NULL,
email varchar(30) NOT NULL,
password varchar(255) NOT NULL);
select * from users;
ALTER TABLE users ADD COLUMN gender ENUM('male', 'female');

insert into users values(101,"Shri","admin","123456789","shri@gmail.com","Shri*12345");
insert into users values(102,"Nidhi","admin","123456987","nidhi@gmail.com","Nidhi*78945");
delete from users where id=101;

select * from users;
create table vehicle(
vehicle_id varchar(20) primary key,
owner varchar(30) NOT NULL,
contact varchar(15) NOT NULL,
type varchar(5) NOT NULL); 

insert into vehicle values("KA25K1234","Shri","897456123","car");

create table parkslot(
slot_id Varchar(5) primary key,
status  enum('occupied','available') NOT NULL);
insert into parkslot values("C1","occupied");
 drop table users;
CREATE TABLE parklog (
    log_id INT PRIMARY KEY AUTO_INCREMENT,
    vehicle_id VARCHAR(20) NOT NULL,
    slot_id Varchar(5) NOT NULL,
    entry_time DATETIME NOT NULL,
    exit_time DATETIME,
    payment DECIMAL(10,2),
    id INT,
    FOREIGN KEY (slot_id) REFERENCES parkslot(slot_id),
    FOREIGN KEY (id) REFERENCES users(id),
    FOREIGN KEY (vehicle_id) REFERENCES vehicle(vehicle_id)
); 
CREATE TABLE staff_logins (
    slno INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    login_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
-- Create the corrected users table
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    role VARCHAR(10) NOT NULL,
    gender ENUM('male','female') NOT NULL,
    contact VARCHAR(15) NOT NULL,
    email VARCHAR(50) NOT NULL,
    password VARCHAR(255) NOT NULL
);
insert into users values(1,"Shri","Admin","Female","7894561230","shri@gmail.com","Shri*12345");
SELECT * FROM USERS;
select * from parklog;
describe users;
INSERT INTO parkslot (slot_id, status) VALUES
('B1', 'available'),
('B2', 'available'),
('B3', 'available'),
('B4', 'available'),
('B5', 'available'),
('B6', 'available'),
('B7', 'available'),
('B8', 'available'),
('B9', 'available'),
('B10', 'available'),
('B11', 'available'),
('B12', 'available'),
('B13', 'available'),
('B14', 'available'),
('B15', 'available'),
('B16', 'available'),
('B17', 'available'),
('B18', 'available'),
('B19', 'available'),
('B20', 'available'),
('B21', 'available'),
('B22', 'available'),
('B23', 'available'),
('B24', 'available'),
('B25', 'available'),
('B26', 'available'),
('B27', 'available'),
('B28', 'available'),
('B29', 'available'),
('B30', 'available'),
('B31', 'available'),
('B32', 'available'),
('B33', 'available'),
('B34', 'available'),
('B35', 'available'),
('B36', 'available');

INSERT INTO parkslot (slot_id, status) VALUES
('C2', 'available'),
('C3', 'available'),
('C4', 'available'),
('C5', 'available'),
('C6', 'available'),
('C7', 'available'),
('C8', 'available'),
('C9', 'available'),
('C10', 'available'),
('C11', 'available'),
('C12', 'available'),
('C13', 'available'),
('C14', 'available'),
('C15', 'available'),
('C16', 'available'),
('C17', 'available'),
('C18', 'available'),
('C19', 'available'),
('C20', 'available'),
('C21', 'available'),
('C22', 'available'),
('C23', 'available'),
('C24', 'available'),
('C25', 'available'),
('C26', 'available'),
('C27', 'available'),
('C28', 'available'),
('C29', 'available'),
('C30', 'available'),
('C31', 'available'),
('C32', 'available'),
('C33', 'available'),
('C34', 'available'),
('C35', 'available'),
('C36', 'available'),
('C37', 'available'),
('C38', 'available'),
('C39', 'available'),
('C40', 'available'),
('C41', 'available'),
('C42', 'available'),
('C43', 'available'),
('C44', 'available'),
('C45', 'available'),
('C46', 'available'),
('C47', 'available'),
('C48', 'available'),
('C49', 'available'),
('C50', 'available'),
('C51', 'available'),
('C52', 'available');
select * from parkslot;
ALTER TABLE parkslot 
  MODIFY status ENUM('available','occupied','not-available') NOT NULL;
