# MathHomeworkAutomarker

Project Description (ASD-STE100 Simplified Technical English)

## Summary

MathHomeworkAutomarker is a web application. It grades mathematics homework automatically. The users are teachers and students in Chinese primary schools and secondary schools.

## The Problem

Teachers must grade many pages of homework by hand. This work takes much time. The system decreases this work. The teacher examines only the questions that the system cannot grade with sufficient confidence.

## How It Works

1. The teacher uploads an answer file (`.docx` or `.pdf`).
2. Each student uploads the homework as a PDF file.
3. The system changes each page of the two files into an image.
4. An AI vision model compares the student pages with the answer pages.
5. The model gives a score and a comment for each question.
6. The teacher can change a score by hand.

The teacher does not have to use a special layout in the answer file. Grading one submission takes approximately 35 to 40 seconds. The system does the grading as a background task.

## Main Functions

- Teachers: create classes and assignments, add students, start the grading, and see the results.
- Students: join a class, upload homework, and see their scores and comments.
- Security: password hashes, login limits, and an invitation code for new teacher accounts.

## Technology

- Backend: Python, FastAPI, and PostgreSQL.
- Frontend: React and TypeScript.
- AI model: Doubao Seed 2.1 Turbo (Volcengine Ark). Qwen is an alternative.
- Deployment: Docker and the Render cloud platform.

## Quality

- 115 backend tests and a browser test with 16 assertions. All the tests pass.
- GitHub Actions runs the tests for each change.
- In a test with real homework, the model matched and graded all 19 questions. A second test with incorrect answers also passed.

## Current Status

All the planned functions are complete. The system is not yet available on the public internet. The deployment configuration is ready. The last step is the activation of a paid hosting account.
