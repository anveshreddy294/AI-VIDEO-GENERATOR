/**
 * VISUALAI : ATELIER CORE DATA & CURRICULUM SOURCES
 * Realistic educational data for Computer Science, Physics, and Biology.
 */

export const ATELIER_SOURCES = [
  {
    id: 'src-db-01',
    name: 'Database Systems Architecture',
    filename: 'Database_Systems_v2_Chapter3.pdf',
    format: 'PDF',
    subject: 'Computer Science',
    pages: 28,
    size: '3.4 MB',
    version: 2,
    status: 'READY',
    conceptsCount: 8,
    coverPlate: '/assets/database_code_screen.jpg',
    opticalConfidence: '99%',
    summary: 'Core relational models, primary and candidate keys, referential integrity, and normalization guidelines.'
  },
  {
    id: 'src-bio-02',
    name: 'Molecular Genetics & Transcription',
    filename: 'Molecular_Biology_Review.pdf',
    format: 'PDF',
    subject: 'Biological Sciences',
    pages: 22,
    size: '2.8 MB',
    version: 1,
    status: 'READY',
    conceptsCount: 6,
    coverPlate: '/assets/biology_cell_microscope.jpg',
    opticalConfidence: '99%',
    summary: 'Double-helix complementary base pairing, hydrogen bonding dynamics, and RNA polymerase transcription.'
  },
  {
    id: 'src-phys-03',
    name: 'Orbital Gravitational Mechanics',
    filename: 'Classical_Mechanics_Lectures.docx',
    format: 'DOCX',
    subject: 'Astrophysics',
    pages: 16,
    size: '1.2 MB',
    version: 1,
    status: 'READY',
    conceptsCount: 5,
    coverPlate: '/assets/astronomy_telescope_galaxy.jpg',
    opticalConfidence: '99%',
    summary: 'Two-body gravitational potentials, orbital speed derivations, and planetary eccentricity laws.'
  },
  {
    id: 'src-analog-04',
    name: 'Active Circuit Schematics & Damping',
    filename: 'Analog_Lab_Notebook_LF356.png',
    format: 'PNG',
    subject: 'Electrical Engineering',
    pages: 1,
    size: '4.1 MB',
    version: 1,
    status: 'READY',
    conceptsCount: 4,
    coverPlate: '/assets/physics_blackboard.jpg',
    opticalConfidence: '98%',
    summary: 'Op-amp feedback loops, frequency responses, and second-order damping ratios in laboratory circuits.'
  }
];

export const ATELIER_CONCEPTS = {
  'relational-model': {
    id: 'relational-model',
    sourceId: 'src-db-01',
    title: 'The Relational Data Model',
    kicker: 'LESSON 01 · DATA TABLES',
    page: 4,
    bbox: [120, 180, 520, 240],
    summary: 'Organizing structured information into tables of rows and columns with defined data types and unique identifiers.',
    explanation: 'A relational table represents an entity type (such as Students or Courses). Each row is a distinct record, and each column contains a single attribute of that record with a strict data type.',
    example: 'Students table with columns (student_id, full_name, enrollment_year), where each row is a registered student.',
    prerequisites: [],
    plateImage: '/assets/database_code_screen.jpg',
    formula: 'Students(student_id, full_name, email, cohort)'
  },
  'primary-key': {
    id: 'primary-key',
    sourceId: 'src-db-01',
    title: 'Entity Integrity & Primary Keys',
    kicker: 'LESSON 02 · CORE PRINCIPLE',
    page: 7,
    bbox: [142, 288, 480, 320],
    summary: 'A unique identifier chosen for each record that can never be empty (NULL) and guarantees every row is distinct.',
    explanation: 'The Entity Integrity rule states that every table must have a primary key attribute (or group of attributes) that uniquely distinguishes each row. Because identity is essential, primary keys can never contain NULL values.',
    example: 'In a University database, student_id (e.g. 104829) is the primary key. Even if two students share the name "Alex Smith", their primary keys ensure they are never confused.',
    prerequisites: ['relational-model'],
    plateImage: '/assets/study_desk_mac.jpg',
    formula: 'Unique(K) AND NOT NULL(K)'
  },
  'foreign-key': {
    id: 'foreign-key',
    sourceId: 'src-db-01',
    title: 'Referential Integrity & Foreign Keys',
    kicker: 'LESSON 03 · TABLE CONNECTIONS',
    page: 12,
    bbox: [80, 140, 540, 360],
    summary: 'Connecting related tables by referencing another table primary key, maintaining cross-table data consistency.',
    explanation: 'A foreign key creates an intentional relationship between two tables. It ensures that a value in a child table (like course_id in an Enrollments table) must always point to an existing valid row in the parent Courses table.',
    example: 'Enrollments(enrollment_id, student_id, course_id) where student_id connects to Students and course_id connects to Courses.',
    prerequisites: ['primary-key'],
    plateImage: '/assets/library_books_hall.jpg',
    formula: 'Foreign_Key(child.id) -> Parent.id'
  },
  'first-normal-form': {
    id: 'first-normal-form',
    sourceId: 'src-db-01',
    title: 'First Normal Form (1NF)',
    kicker: 'LESSON 04 · CLEAN SCHEMAS',
    page: 18,
    bbox: [100, 220, 500, 300],
    summary: 'Ensuring that every cell in a table contains only a single atomic value and no repeating groups.',
    explanation: 'First Normal Form requires that each attribute column holds atomic (indivisible) values. Instead of packing multiple phone numbers or tags into a single text cell with commas, each value must have its own separate record or table.',
    example: 'Splitting "phone_numbers: 555-0101, 555-0102" into individual rows in a dedicated student_phones table.',
    prerequisites: ['relational-model', 'primary-key'],
    plateImage: '/assets/math_geometry_compass.jpg',
    formula: 'Atomic(Attribute_Value) == True'
  }
};

export const ATELIER_ASSESSMENT_QUESTIONS = [
  {
    id: 'q-pk-01',
    conceptId: 'primary-key',
    prompt: 'Which condition is mandatory for any column chosen as a primary key in a relational database?',
    options: [
      'It must be strictly unique for every row and cannot contain a NULL (empty) value.',
      'It must be an auto-incrementing number generated automatically by the computer.',
      'It must reference a matching key in an external parent table.',
      'It must contain only alphabet letters without any numbers.'
    ],
    answer: 0,
    misconception: 'Confusing auto-increment numbers with the fundamental rule of primary key uniqueness and non-null values.',
    explanation: 'Entity Integrity requires that primary keys uniquely identify each record, so null values are never allowed.'
  },
  {
    id: 'q-fk-02',
    conceptId: 'foreign-key',
    prompt: 'When is a foreign key column allowed to have a NULL value in a relational table?',
    options: [
      'Never; foreign keys can never be null under any circumstances.',
      'When the relationship is optional and a record does not have a parent association yet.',
      'Only when the table has fewer than 50 total records.',
      'Only when the table is temporarily locked for maintenance.'
    ],
    answer: 1,
    misconception: 'Assuming foreign keys must always be non-null, forgetting that optional relationships (0 to 1) exist.',
    explanation: 'Unless explicitly marked as NOT NULL, a foreign key can be null to show that no parent link exists for that specific row.'
  },
  {
    id: 'q-1nf-03',
    conceptId: 'first-normal-form',
    prompt: 'A table column stores "Physics, Calculus, Art" in a single text field. What does 1NF require you to do?',
    options: [
      'Keep the comma-separated list and parse it in your application code.',
      'Compress the column with zip compression to save disk space.',
      'Separate the values so each entry is atomic, storing items across individual rows or a related table.',
      'Create a second table with duplicate copies of the entire database.'
    ],
    answer: 2,
    misconception: 'Storing multiple values in a single column instead of enforcing clean relational atomicity.',
    explanation: 'First Normal Form requires atomic (single) values in each table cell, avoiding comma-separated lists.'
  },
  {
    id: 'q-pk-04',
    conceptId: 'primary-key',
    prompt: 'Can a relational table have more than one primary key?',
    options: [
      'No; a table can only have one primary key, although it can be composed of multiple columns.',
      'Yes; a table typically has 2 to 5 primary keys by default.',
      'Yes; every numeric column automatically becomes an independent primary key.',
      'Only in NoSQL document databases, never in relational databases.'
    ],
    answer: 0,
    misconception: 'Confusing a composite primary key (multiple columns forming one key) with having multiple distinct primary keys.',
    explanation: 'A table can only have ONE primary key constraint. When multiple columns work together as the key, it is called a composite primary key.'
  },
  {
    id: 'q-rel-05',
    conceptId: 'relational-model',
    prompt: 'In relational database terminology, what does a "tuple" correspond to in everyday table terms?',
    options: [
      'A column header',
      'A single table row (record)',
      'The data type of a cell',
      'The table title'
    ],
    answer: 1,
    misconception: 'Mixing up tuples (rows) and attributes (columns).',
    explanation: 'In the formal relational model, a relation is a table, an attribute is a column, and a tuple is an individual row.'
  },
  {
    id: 'q-pk-06',
    conceptId: 'primary-key',
    prompt: 'What is a "Composite Primary Key"?',
    options: [
      'A primary key made by combining two or more columns together to uniquely identify a row.',
      'A primary key that automatically creates a backup copy on another server.',
      'A primary key made of random letters generated by an algorithm.',
      'A key that only works when connected to the internet.'
    ],
    answer: 0,
    misconception: 'Assuming keys can only ever consist of a single column.',
    explanation: 'A composite primary key uses a combination of multiple columns (e.g., student_id + course_id) to guarantee row uniqueness.'
  },
  {
    id: 'q-fk-07',
    conceptId: 'foreign-key',
    prompt: 'What happens if you try to insert a foreign key value that does not exist in the referenced parent table?',
    options: [
      'The database allows it and leaves the parent table empty.',
      'The database throws a Foreign Key Constraint violation error and prevents the insert.',
      'The database automatically creates a blank dummy row in the parent table.',
      'The computer restarts automatically.'
    ],
    answer: 1,
    misconception: 'Assuming the database will silently create missing parent rows.',
    explanation: 'Referential integrity protects data by rejecting any child record whose foreign key does not match an existing parent row.'
  },
  {
    id: 'q-1nf-08',
    conceptId: 'first-normal-form',
    prompt: 'Which of the following violates First Normal Form (1NF)?',
    options: [
      'A column named "email" storing one email address per student.',
      'A column named "hobbies" containing "Swimming, Reading, Chess" in a single field.',
      'A column named "enrollment_date" containing a standard calendar date.',
      'A column named "is_active" storing a true/false boolean flag.'
    ],
    answer: 1,
    misconception: 'Failing to spot multi-valued list attributes inside table cells.',
    explanation: 'A single cell with a list of hobbies violates 1NF because the values are not atomic.'
  },
  {
    id: 'q-rel-09',
    conceptId: 'relational-model',
    prompt: 'Why are duplicate rows forbidden in a strict relational table?',
    options: [
      'Because mathematical sets by definition cannot contain identical duplicate elements.',
      'Because computers run out of memory if two rows have similar names.',
      'Because databases cannot display tables with more than 10 rows.',
      'Because SQL commands only support odd numbers of rows.'
    ],
    answer: 0,
    misconception: 'Believing uniqueness is just a storage optimization rather than a mathematical set theory rule.',
    explanation: 'A relational table is based on mathematical set theory, where a set contains distinct elements without duplicates.'
  },
  {
    id: 'q-pk-10',
    conceptId: 'primary-key',
    prompt: 'What is a "Surrogate Key"?',
    options: [
      'A naturally occurring business identifier like a passport number.',
      'An artificially generated identifier (like an auto-incrementing ID or UUID) created solely for database management.',
      'A password used by the database administrator.',
      'A key borrowed from another table temporarily.'
    ],
    answer: 1,
    misconception: 'Confusing natural keys (like passport or tax IDs) with synthetic surrogate keys (like auto-increment IDs).',
    explanation: 'A surrogate key has no business meaning in the real world; it is generated purely as an efficient, immutable primary key for the database.'
  },
  {
    id: 'q-fk-11',
    conceptId: 'foreign-key',
    prompt: 'What does "CASCADE DELETE" do when configured on a foreign key relationship?',
    options: [
      'Deletes the entire database when any record is edited.',
      'Automatically deletes all child rows when the corresponding parent row is deleted.',
      'Prevents any user from deleting records permanently.',
      'Saves the deleted record into a separate backup file.'
    ],
    answer: 1,
    misconception: 'Thinking CASCADE delete deletes the parent when the child is deleted, rather than child rows when parent is deleted.',
    explanation: 'CASCADE DELETE automatically cleans up associated child rows when their parent record is removed, preventing orphan rows.'
  },
  {
    id: 'q-1nf-12',
    conceptId: 'first-normal-form',
    prompt: 'Why is 1NF beneficial for querying and filtering data in SQL?',
    options: [
      'It allows standard SQL queries (like WHERE and JOIN) to search individual values cleanly without string matching.',
      'It reduces table column width to zero bytes.',
      'It turns all numbers into uppercase characters.',
      'It prevents users from using passwords.'
    ],
    answer: 0,
    misconception: 'Underestimating how difficult it is to query and index comma-separated strings inside SQL columns.',
    explanation: 'With atomic values, indexing and filtering (e.g. `WHERE hobby = "Chess"`) are fast, clean, and exact.'
  },
  {
    id: 'q-rel-13',
    conceptId: 'relational-model',
    prompt: 'What is the primary difference between a Candidate Key and a Primary Key?',
    options: [
      'A candidate key is a column that could qualify as a primary key; the primary key is the one chosen by the designer.',
      'Candidate keys are only used during testing and deleted before launch.',
      'Candidate keys can never hold numbers, only text.',
      'Candidate keys are stored on the user laptop while primary keys stay on the server.'
    ],
    answer: 0,
    misconception: 'Assuming all candidate keys are separate primary keys.',
    explanation: 'Candidate keys are all possible minimal superkeys that satisfy uniqueness; the designer selects one to be the official primary key.'
  },
  {
    id: 'q-pk-14',
    conceptId: 'primary-key',
    prompt: 'Why is a Social Security Number (SSN) often discouraged as a primary key in modern systems?',
    options: [
      'Because privacy regulations, identity theft risks, and foreign users without an SSN make natural keys problematic.',
      'Because databases cannot store 9-digit numbers.',
      'Because numbers cannot be sorted alphabetically.',
      'Because SSNs change every month.'
    ],
    answer: 0,
    misconception: 'Assuming unique real-world identifiers are always good primary keys regardless of privacy and universality.',
    explanation: 'Natural identifiers often have privacy implications or might not exist for every user; surrogate IDs avoid these pitfalls.'
  },
  {
    id: 'q-fk-15',
    conceptId: 'foreign-key',
    prompt: 'Can a foreign key reference a column in the same table it resides in?',
    options: [
      'Yes; this is known as a recursive or self-referencing relationship (e.g., manager_id pointing to employee_id).',
      'No; foreign keys must strictly link across two completely separate databases.',
      'No; circular references cause an instant syntax error in all SQL engines.',
      'Only if the table name is less than 5 characters.'
    ],
    answer: 0,
    misconception: 'Believing foreign keys can only reference other tables.',
    explanation: 'Self-referencing foreign keys are standard for hierarchical data, such as an employee pointing to their manager in the same Employees table.'
  },
  {
    id: 'q-1nf-16',
    conceptId: 'first-normal-form',
    prompt: 'If a table has columns `item_1`, `item_2`, `item_3`, what rule does this design pattern violate?',
    options: [
      'It creates a repeating group of attributes, violating the spirit of First Normal Form (1NF).',
      'It violates the operating system file permissions.',
      'It violates the SQL keyword capitalization convention.',
      'It prevents the table from having any primary key.'
    ],
    answer: 0,
    misconception: 'Numbering columns to store multiple items instead of structuring them in a related table.',
    explanation: 'Having multiple numbered columns for the same concept (`phone1`, `phone2`, `phone3`) is a classic anti-pattern violating 1NF principles.'
  },
  {
    id: 'q-rel-17',
    conceptId: 'relational-model',
    prompt: 'What does "Domain" mean in the relational model?',
    options: [
      'The website URL where the database is hosted.',
      'The set of permitted, valid values and data types for a given column (e.g. positive integers, dates).',
      'The company that purchased the server hardware.',
      'The network router name.'
    ],
    answer: 1,
    misconception: 'Confusing an internet web domain with a relational mathematical domain of allowable values.',
    explanation: 'In relational algebra, an attribute domain defines the valid pool of values (data type and constraints) that can appear in that attribute.'
  },
  {
    id: 'q-pk-18',
    conceptId: 'primary-key',
    prompt: 'What is the main benefit of an immutable (unchanging) primary key?',
    options: [
      'It prevents foreign key references across dependent child tables from breaking or needing complex cascading updates.',
      'It speeds up monitor refresh rates.',
      'It makes the database backup files smaller.',
      'It allows non-administrators to change passwords.'
    ],
    answer: 0,
    misconception: 'Thinking primary key values can be casually edited without impacting all related tables.',
    explanation: 'If a primary key changes, all foreign key pointers across the database must also update, which is slow and prone to orphan bugs.'
  },
  {
    id: 'q-fk-19',
    conceptId: 'foreign-key',
    prompt: 'What is an "Orphan Record" in database management?',
    options: [
      'A child record whose foreign key points to a parent record that no longer exists.',
      'A record created before the database was backed up.',
      'A row that has only numbers and no letters.',
      'A table with zero columns.'
    ],
    answer: 0,
    misconception: 'Not understanding how referential integrity constraints prevent dangling pointers.',
    explanation: 'An orphan record occurs when a parent row is deleted without cleaning up its child references, leaving meaningless pointer values.'
  },
  {
    id: 'q-1nf-20',
    conceptId: 'first-normal-form',
    prompt: 'Which step completes normalizing an unnormalized order table with repeated item lists into 1NF?',
    options: [
      'Move individual items into a separate Order_Items line table linked by order_id, ensuring atomic fields.',
      'Encrypt the order text using 256-bit AES encryption.',
      'Remove all item names and only record the total dollar price.',
      'Convert the table into a CSV file on the desktop.'
    ],
    answer: 0,
    misconception: 'Removing detailed data rather than structuring it into an associated line items table.',
    explanation: 'Extracting repeating items into an `Order_Items` table with an `order_id` foreign key achieves 1NF while preserving every item detail.'
  }
];

export const ATELIER_VIDEO_STORYBOARD = [
  {
    sceneIndex: 1,
    time: '00:00 - 00:20',
    title: 'Introduction to Primary Keys & Record Uniqueness',
    summary: 'Why every table record needs an unambiguous, non-null identity.',
    thumb: '/assets/student_studying.jpg',
    plate: '/assets/study_desk_mac.jpg',
    status: 'Lesson Ready'
  },
  {
    sceneIndex: 2,
    time: '00:20 - 00:45',
    title: 'Entity Integrity Rule in Action',
    summary: 'Visual walkthrough of duplicate checks and why NULL values break queries.',
    thumb: '/assets/database_code_screen.jpg',
    plate: '/assets/notebook_handwritten.jpg',
    status: 'Lesson Ready'
  },
  {
    sceneIndex: 3,
    time: '00:45 - 01:10',
    title: 'Natural Keys vs Surrogate Auto-Increment IDs',
    summary: 'Comparing real-world identifiers with efficient synthetic database keys.',
    thumb: '/assets/physics_blackboard.jpg',
    plate: '/assets/library_books_hall.jpg',
    status: 'Lesson Ready'
  },
  {
    sceneIndex: 4,
    time: '01:10 - 01:30',
    title: 'Summary, Best Practices & Practice Checkpoint',
    summary: 'Reviewing key principles and preparing for diagnostic practice questions.',
    thumb: '/assets/math_geometry_compass.jpg',
    plate: '/assets/study_desk_mac.jpg',
    status: 'Lesson Ready'
  }
];

export const ATELIER_EDUCATOR_ANALYTICS = {
  courseName: 'CS 304: Relational Database Systems',
  enrolledStudents: 64,
  averageMastery: '81%',
  misconceptionAlerts: [
    {
      conceptId: 'foreign-key',
      conceptTitle: 'Nullable Foreign Keys vs Primary Keys',
      flaggedCount: 19,
      severity: 'Review Recommended',
      explanation: '30% of students assumed foreign keys must always be non-null, forgetting optional associations.'
    },
    {
      conceptId: 'first-normal-form',
      conceptTitle: 'Storing Lists in a Single Column',
      flaggedCount: 11,
      severity: 'Minor Review',
      explanation: '17% of students attempted comma-separated lists rather than creating a clean junction table.'
    }
  ]
};
