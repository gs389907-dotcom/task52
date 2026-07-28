# Online Job Portal

A professional online job portal built with Flask, SQLite, HTML, CSS, and JavaScript. The platform supports job seekers and admins with full CRUD operations, search, filters, uploads, applications, saved jobs, and a responsive UI.

## Features

### Job Seeker
- Register, login, logout
- Edit profile and upload resume
- Search and filter jobs
- View job details
- Apply for jobs
- Track applied jobs
- Save and remove favourite jobs

### Admin
- Secure admin login
- Dashboard with statistics
- Add, edit, and delete jobs
- View registered users
- View and update applications
- Delete users

## Folder Structure

```text
OnlineJobPortal/
├── app.py
├── requirements.txt
├── README.md
├── database.db
├── static/
│   ├── css/
│   ├── js/
│   └── images/
├── templates/
│   ├── index.html
│   ├── about.html
│   ├── register.html
│   ├── login.html
│   ├── dashboard.html
│   ├── profile.html
│   ├── jobs.html
│   ├── job_details.html
│   ├── apply.html
│   ├── saved_jobs.html
│   ├── applications.html
│   ├── admin_login.html
│   ├── admin_dashboard.html
│   ├── add_job.html
│   ├── edit_job.html
│   ├── manage_jobs.html
│   ├── manage_users.html
│   ├── manage_applications.html
│   └── 404.html
└── uploads/
```

## Installation

```bash
python -m venv venv
source venv/bin/activate  # On Windows use venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Default Admin Login

- Username: admin
- Password: admin123

## Deployment

The app is ready for deployment on Render. Set the environment variable `PORT` to the port provided by Render.

## Screenshots Placeholder

Add screenshots of the home page, dashboard, and admin panel here after deployment.
