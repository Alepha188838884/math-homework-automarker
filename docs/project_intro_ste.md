# MathHomeworkAutomarker: Project Description

Language standard: ASD-STE100 Simplified Technical English.

## 1. Summary

MathHomeworkAutomarker is a web application. It grades mathematics homework automatically.

The users are teachers and students in Chinese primary schools and secondary schools. The user interface is in Chinese.

A teacher uploads one answer file for each assignment. Each student uploads the homework as a PDF file. The system then uses an AI vision model to find each question, give a score, and write a comment.

## 2. The Problem

Teachers often give mathematics homework. Each teacher must grade many pages by hand. This work takes much time.

When grading takes much time, the teacher has less time to prepare lessons and to help students. Students also wait longer for their results.

The system decreases this manual work. The teacher examines only the questions that the system cannot grade with sufficient confidence.

## 3. Functions for Teachers

A teacher can do these tasks:

- Create a class and get a join link for the students.
- Add students to a class and reset the password of a student.
- Create an assignment with a due date.
- Upload one answer file for each assignment. The file can be a `.docx` file or a `.pdf` file.
- Start the grading of one submission or of all the submissions for an assignment.
- See the status of each submission and the score of each question.
- Change the score of a question by hand. The system then calculates the total score again.
- Delete a class, an assignment, or a student.

The system can require an invitation code for new teacher accounts. This prevents unwanted registrations.

## 4. Functions for Students

A student can do these tasks:

- Join a class with the join link from the teacher, and then log in.
- See the list of assignments and the status of each submission.
- Upload the homework as one PDF file.
- Upload the homework again. The new file replaces the old file, and the system deletes the old results.
- See the score and the comment for each question.

A student can see only his or her own results. A request for the results of a different student gets an error.

## 5. How the Grading Works

The grading process has these steps:

1. The teacher uploads the answer file. The system keeps the file on the server.
2. If the answer file is a `.docx` file, the system converts it to a PDF file. The system uses LibreOffice for this conversion.
3. The system renders each page of the answer file as an image. The system uses PyMuPDF for this step.
4. The system also renders each page of the student PDF file as an image.
5. The system sends all the page images to the vision model in one request.
6. The vision model finds each question in the answer file. It then finds the related answer in the student pages.
7. For each question, the model gives the score, the maximum score, a "correct" or "incorrect" decision, and a comment. The model sends this data in JSON format.
8. The system normalizes the data and keeps it in the database.

The teacher does not have to use a special layout in the answer file. The vision model reads the full document and matches the questions.

The default vision model is Doubao Seed 2.1 Turbo. The system connects to it through the Volcengine Ark API. The system can also use a Qwen model from Alibaba Cloud as an alternative.

## 6. Result Status and Manual Review

Each submission gets one of two result types:

- `graded`: The system gave a score to all the questions.
- `needs_manual_review`: The model could not match or grade one or more questions with sufficient confidence.

For the `needs_manual_review` status, the system shows only the subtotal of the automatic scores. The teacher examines the open questions and gives a score by hand. When the teacher gives a score to the last open question, the status changes to `graded`.

## 7. Background Grading

Grading one submission takes approximately 35 to 40 seconds. For this reason, the system does the grading as a background task.

When the teacher starts the grading, the server immediately sends a reply with the HTTP 202 status. The web page then asks the server for the status approximately every 10 seconds.

The system prevents two grading tasks on the same submission at the same time. A second request gets the HTTP 409 status.

If the server stops during a grading task, the system finds this submission at the next start. It then sets the status of the submission to `failed_grading`. The teacher can then start the grading again.

## 8. Technical Architecture

The backend uses these components:

- Python 3.11 and the FastAPI web framework.
- SQLAlchemy for the database access and Alembic for the database migrations.
- A PostgreSQL database in the production configuration.
- LibreOffice for the conversion of `.docx` files to PDF files.
- PyMuPDF for the conversion of PDF pages to images.
- The OpenAI-compatible API format for the connection to the vision model.

The frontend uses React, TypeScript, and Vite. The layout operates on desktop screens and on mobile phone screens.

## 9. Security Measures

The system has these security measures:

- The system uses JSON Web Tokens (JWT) for the login sessions of teachers and students.
- The system keeps passwords only as PBKDF2-SHA256 hashes.
- Each password must have a minimum of 8 characters.
- The system accepts a maximum of 10 login and registration requests in 60 seconds from one IP address.
- The maximum size of an uploaded file is 20 MB.
- The server accepts requests only from a fixed list of web addresses. It does not accept a wildcard setting.

## 10. Tests and Quality

The project has these automatic tests:

- 115 backend tests. All of these tests pass.
- An end-to-end test with 16 assertions. This test uses Playwright to operate a real web browser.
- The end-to-end test examines all the pages, the status labels, the layout at 320 and 375 pixel screen widths, and browser errors.

GitHub Actions runs three automatic workflows for each change. The first workflow runs the backend tests. The second workflow builds the frontend. The third workflow builds the Docker image.

The project also has a separate validation tool for the vision model. The developer used this tool before the integration of the model into the main system.

## 11. Grading Quality Validation

The first validation test used a real answer file and a real homework file. The answer file had 7 pages after the conversion. The homework file had 2 pages and 19 questions.

The model matched all 19 questions. It graded all 19 questions automatically. The developer examined these results by hand.

The second validation test used homework with incorrect answers. This test makes sure that the model does not give scores that are too high. The developer examined the results, and this test also passed.

## 12. Development Process

The project started in March 2026. Most of the work occurred from July 2026 to September 2026.

The first version extracted the text from the answer file. That version required a special layout in the answer file. The current version sends page images to the vision model. This change removed the layout requirement and made the system easier to use.

Each change went through a separate review step before the change went into the main code. These reviews found four serious defects before the release. Two examples are a database address format error and a file conversion lock problem. The developer corrected all four defects and added tests for them.

The project also has a user guide in Chinese for teachers. The guide does not use technical language.

## 13. Current Status

All the planned functions are complete. All the automatic tests pass.

The developer did a full test of the production process on a local computer. This test used the real vision model. The grading took 40 seconds, and the model matched and graded all 19 questions.

The Docker image builds correctly in the automatic workflow. The deployment configuration for the Render cloud platform is ready.

The system is not yet available on the public internet. The last step is the activation of a paid hosting account.
