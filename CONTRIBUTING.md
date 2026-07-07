# Contributing to CogniOS

First off, thank you for taking the time to contribute to **CogniOS**! 🎉

Whether you're fixing a bug, implementing a new feature, improving documentation, or optimizing existing code, your contributions are appreciated.

Please read this guide before making your first contribution.

---

# Development Workflow

All development follows the GitHub Issue → Branch → Pull Request workflow.

```
Issue
   ↓
Assign Yourself
   ↓
Create a Branch
   ↓
Implement Changes
   ↓
Commit & Push
   ↓
Open Pull Request
   ↓
Code Review
   ↓
Merge
```

Direct pushes to the `main` branch are **not allowed**.

---

# Before You Start

Before working on a feature:

1. Check the existing GitHub Issues.
2. Assign the issue to yourself.
3. If the required issue does not exist, create one describing the proposed feature or bug.
4. Wait for approval (if required) before beginning implementation.

This helps prevent duplicate work and keeps development organized.

---

# Branch Naming Convention

Create a new branch from the latest `main` branch.

Use the following naming convention:

```
feature/<short-description>
fix/<short-description>
docs/<short-description>
refactor/<short-description>
test/<short-description>
```

Examples:

```
feature/process-monitor
feature/anomaly-detector
fix/cpu-parser
docs/backend-api
refactor/cache-layer
```

---

# Coding Standards

Please ensure your code follows these guidelines:

* Write clean and readable code.
* Use meaningful variable and function names.
* Follow the coding style used within the module.
* Keep functions small and focused.
* Avoid unnecessary complexity.
* Remove unused code before submitting a Pull Request.
* Add comments only where they improve understanding.

---

# Documentation

Every contribution should include documentation updates whenever applicable.

Documentation may include:

* Function descriptions
* API endpoint updates
* Architecture changes
* README updates
* Module documentation

If your implementation changes the behavior of a module, its documentation should also be updated.

---

# Commit Message Guidelines

Write clear and descriptive commit messages.

Recommended format:

```
feat: implement process telemetry collector
fix: resolve memory parsing issue
docs: update backend documentation
refactor: simplify scheduler logic
test: add telemetry unit tests
```

Avoid vague commit messages such as:

```
update
changes
fixed stuff
final
temp
```

---

# Pull Request Guidelines

Before opening a Pull Request:

* Ensure your branch is up to date.
* Resolve merge conflicts.
* Verify the project builds successfully.
* Update relevant documentation.
* Ensure code follows project conventions.

Each Pull Request should focus on **one feature or one bug fix**.

Large unrelated changes should be split into multiple Pull Requests.

---

# Code Review

Every Pull Request will be reviewed before merging.

Reviewers may request:

* Code improvements
* Refactoring
* Additional documentation
* Bug fixes
* Performance improvements

Please address review comments before requesting another review.

---

# Testing

Before submitting a Pull Request, verify that:

* The project builds successfully.
* Existing functionality remains unaffected.
* New functionality works as intended.
* Any applicable tests pass successfully.

Do not submit code that does not compile.

---

# Reporting Bugs

When reporting a bug, include:

* Description of the issue
* Steps to reproduce
* Expected behavior
* Actual behavior
* Relevant logs or screenshots (if available)

---

# Feature Requests

When proposing a new feature, include:

* Problem being solved
* Proposed solution
* Module(s) affected
* Expected outcome

Discuss major architectural changes before beginning implementation.

---

# Code of Conduct

Please be respectful and collaborative.

Constructive discussions and code reviews help improve the project for everyone.

---

# Questions

If you have questions regarding implementation, architecture, or project structure, please open a GitHub Discussion or contact the maintainers before starting work.

Happy coding! 🚀
