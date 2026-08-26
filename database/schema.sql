-- ICMS database schema (PostgreSQL)
-- Auto-generated from SQLAlchemy models. 41 tables.

CREATE TABLE applications (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	applicant_name VARCHAR, 
	email VARCHAR, 
	program_id VARCHAR, 
	program_name VARCHAR, 
	score FLOAT, 
	status VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE approval_limits (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	scope_level VARCHAR, 
	process VARCHAR, 
	threshold FLOAT, 
	PRIMARY KEY (id)
);

CREATE TABLE assets (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	tag VARCHAR, 
	name VARCHAR, 
	category VARCHAR, 
	location VARCHAR, 
	status VARCHAR, 
	value FLOAT, 
	PRIMARY KEY (id)
);

CREATE TABLE audit_logs (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR, 
	actor VARCHAR, 
	actor_name VARCHAR, 
	office_n INTEGER, 
	action VARCHAR, 
	entity VARCHAR, 
	prev_state VARCHAR, 
	new_state VARCHAR, 
	reason VARCHAR, 
	ip VARCHAR, 
	device VARCHAR, 
	auth_level VARCHAR, 
	prev_hash VARCHAR, 
	hash VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE books (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	isbn VARCHAR, 
	title VARCHAR, 
	author VARCHAR, 
	category VARCHAR, 
	copies_total INTEGER, 
	copies_available INTEGER, 
	PRIMARY KEY (id)
);

CREATE TABLE budget_lines (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	campus VARCHAR, 
	category VARCHAR, 
	allocated FLOAT, 
	spent FLOAT, 
	fiscal_year VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE complaints (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	kind VARCHAR, 
	raised_by VARCHAR, 
	subject VARCHAR, 
	detail TEXT, 
	status VARCHAR, 
	severity VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE delegations (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	from_user VARCHAR, 
	to_user VARCHAR, 
	authority VARCHAR, 
	scope_ref VARCHAR, 
	"limit" FLOAT, 
	start TIMESTAMP WITHOUT TIME ZONE, 
	"end" TIMESTAMP WITHOUT TIME ZONE, 
	status VARCHAR, 
	reason VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE departments (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	code VARCHAR, 
	name VARCHAR, 
	campus VARCHAR, 
	hod_person_id VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE hostel_rooms (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	block VARCHAR, 
	room_no VARCHAR, 
	capacity INTEGER, 
	occupied INTEGER, 
	PRIMARY KEY (id)
);

CREATE TABLE job_postings (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	title VARCHAR, 
	dept VARCHAR, 
	kind VARCHAR, 
	openings INTEGER, 
	status VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE notifications (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	user_id VARCHAR, 
	severity VARCHAR, 
	title VARCHAR, 
	body VARCHAR, 
	read BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE org_scopes (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	level VARCHAR, 
	name VARCHAR, 
	parent_id VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(parent_id) REFERENCES org_scopes (id)
);

CREATE TABLE permissions (
	id VARCHAR NOT NULL, 
	resource VARCHAR, 
	action VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE persons (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	name VARCHAR, 
	email VARCHAR, 
	contact VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE placement_drives (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	company VARCHAR, 
	role VARCHAR, 
	ctc FLOAT, 
	date DATE, 
	eligible_cgpa FLOAT, 
	status VARCHAR, 
	offers INTEGER, 
	PRIMARY KEY (id)
);

CREATE TABLE research_projects (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	title VARCHAR, 
	pi_name VARCHAR, 
	dept VARCHAR, 
	agency VARCHAR, 
	grant_amount FLOAT, 
	status VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE role_permissions (
	id VARCHAR NOT NULL, 
	role_id VARCHAR, 
	office_n INTEGER, 
	action VARCHAR, 
	authority VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE roles (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	office_n INTEGER, 
	name VARCHAR, 
	category VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE staff_members (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	emp_id VARCHAR, 
	name VARCHAR, 
	email VARCHAR, 
	phone VARCHAR,
	office_hours VARCHAR,
	dept_id VARCHAR, 
	designation VARCHAR, 
	office_n INTEGER, 
	campus VARCHAR, 
	status VARCHAR, 
	date_joined DATE, 
	user_id VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE tenants (
	id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE transport_routes (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	name VARCHAR, 
	stops VARCHAR, 
	vehicle_no VARCHAR, 
	seats INTEGER, 
	seats_taken INTEGER, 
	PRIMARY KEY (id)
);

CREATE TABLE workflow_instances (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	process_key VARCHAR, 
	label VARCHAR, 
	office_n INTEGER, 
	title VARCHAR, 
	state VARCHAR, 
	amount FLOAT, 
	initiator_id VARCHAR, 
	initiator_name VARCHAR, 
	current_stage INTEGER, 
	scope_level VARCHAR, 
	escalated BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE approvals (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	workflow_id VARCHAR, 
	actor_id VARCHAR, 
	actor_name VARCHAR, 
	stage INTEGER, 
	stage_label VARCHAR, 
	decision VARCHAR, 
	authority VARCHAR, 
	reason VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workflow_id) REFERENCES workflow_instances (id)
);

CREATE TABLE book_loans (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	book_id VARCHAR, 
	borrower VARCHAR, 
	borrower_name VARCHAR, 
	issued_on DATE, 
	due_on DATE, 
	returned BOOLEAN, 
	fine FLOAT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(book_id) REFERENCES books (id)
);

CREATE TABLE courses (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	dept_id VARCHAR, 
	code VARCHAR, 
	title VARCHAR, 
	credits INTEGER, 
	semester INTEGER, 
	description TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(dept_id) REFERENCES departments (id)
);

CREATE TABLE designations (
	id VARCHAR NOT NULL, 
	person_id VARCHAR, 
	title VARCHAR, 
	employee_id VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(person_id) REFERENCES persons (id)
);

CREATE TABLE hostel_allocations (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	room_id VARCHAR, 
	student_id VARCHAR, 
	student_name VARCHAR, 
	status VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(room_id) REFERENCES hostel_rooms (id)
);

CREATE TABLE leave_requests (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	staff_id VARCHAR, 
	staff_name VARCHAR, 
	kind VARCHAR, 
	from_date DATE, 
	to_date DATE, 
	days INTEGER, 
	reason VARCHAR, 
	status VARCHAR, 
	decided_by VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(staff_id) REFERENCES staff_members (id)
);

CREATE TABLE programs (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	dept_id VARCHAR, 
	code VARCHAR, 
	name VARCHAR, 
	level VARCHAR, 
	duration_years INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(dept_id) REFERENCES departments (id)
);

CREATE TABLE users (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	person_id VARCHAR, 
	username VARCHAR, 
	password_hash VARCHAR, 
	status VARCHAR, 
	mfa_enabled BOOLEAN, 
	office_n INTEGER, 
	role VARCHAR, 
	scope_level VARCHAR, 
	scope_ref VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(person_id) REFERENCES persons (id)
);

CREATE TABLE sections (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	course_id VARCHAR, 
	dept_id VARCHAR, 
	term VARCHAR, 
	section_code VARCHAR, 
	faculty_person_id VARCHAR, 
	room VARCHAR, 
	schedule VARCHAR, 
	capacity INTEGER, 
	scope_ref VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(course_id) REFERENCES courses (id), 
	FOREIGN KEY(dept_id) REFERENCES departments (id)
);

CREATE TABLE students (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	roll_no VARCHAR, 
	name VARCHAR, 
	email VARCHAR, 
	program_id VARCHAR, 
	dept_id VARCHAR, 
	campus VARCHAR, 
	batch VARCHAR, 
	semester INTEGER, 
	section VARCHAR, 
	status VARCHAR, 
	cgpa FLOAT, 
	hosteller BOOLEAN, 
	scholarship BOOLEAN, 
	user_id VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(program_id) REFERENCES programs (id), 
	FOREIGN KEY(dept_id) REFERENCES departments (id)
);

CREATE TABLE user_roles (
	id VARCHAR NOT NULL, 
	user_id VARCHAR, 
	role_id VARCHAR, 
	org_scope_id VARCHAR, 
	valid_from TIMESTAMP WITHOUT TIME ZONE, 
	valid_to TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(role_id) REFERENCES roles (id)
);

CREATE TABLE assessments (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	section_id VARCHAR, 
	name VARCHAR, 
	max_marks FLOAT, 
	weight FLOAT, 
	locked BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(section_id) REFERENCES sections (id)
);

CREATE TABLE attendance_records (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	section_id VARCHAR, 
	student_id VARCHAR, 
	on_date DATE, 
	present BOOLEAN, 
	marked_by VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(section_id) REFERENCES sections (id), 
	FOREIGN KEY(student_id) REFERENCES students (id)
);

CREATE TABLE enrollments (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	student_id VARCHAR, 
	section_id VARCHAR, 
	status VARCHAR, 
	requested_at TIMESTAMP WITHOUT TIME ZONE, 
	grade VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(section_id) REFERENCES sections (id)
);

CREATE TABLE fee_invoices (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	student_id VARCHAR, 
	term VARCHAR, 
	amount FLOAT, 
	paid FLOAT, 
	status VARCHAR, 
	due_date DATE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(student_id) REFERENCES students (id)
);

CREATE TABLE result_sheets (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	section_id VARCHAR, 
	term VARCHAR, 
	status VARCHAR, 
	published_by VARCHAR, 
	published_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(section_id) REFERENCES sections (id)
);

CREATE TABLE marks (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	assessment_id VARCHAR, 
	student_id VARCHAR, 
	score FLOAT, 
	entered_by VARCHAR, 
	entered_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(assessment_id) REFERENCES assessments (id), 
	FOREIGN KEY(student_id) REFERENCES students (id)
);

CREATE TABLE payments (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	invoice_id VARCHAR, 
	student_id VARCHAR, 
	amount FLOAT, 
	method VARCHAR, 
	at TIMESTAMP WITHOUT TIME ZONE, 
	reference VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(invoice_id) REFERENCES fee_invoices (id)
);
