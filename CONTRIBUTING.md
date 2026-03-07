# Contributing to PLOS-backend

Thank you for your interest in contributing to PLOS-backend! We welcome contributions from the community to help improve this project.

## Code of Conduct

This project follows a code of conduct to ensure a welcoming environment for all contributors. Please be respectful and considerate in your interactions.

## How to Contribute

### Reporting Issues

- Use the GitHub issue tracker to report bugs or request features.
- Provide as much detail as possible, including steps to reproduce the issue.
- Check existing issues to avoid duplicates.

### Contributing Code

1. **Fork the repository** on GitHub.
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/PLOS-backend.git
   cd PLOS-backend
   ```
3. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Set up the development environment**:
   - Follow the setup instructions in [LOCAL_SETUP.md](docs/LOCAL_SETUP.md)
   - Install dependencies and run tests to ensure everything works.
5. **Make your changes**:
   - Follow the coding standards below.
   - Write tests for new features or bug fixes.
   - Ensure all tests pass.
6. **Commit your changes**:
   - Use clear, descriptive commit messages.
   - Reference issue numbers if applicable (e.g., "Fix #123: Description").
7. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```
8. **Create a Pull Request**:
   - Go to the original repository on GitHub.
   - Click "New Pull Request".
   - Provide a clear description of your changes.
   - Reference any related issues.

### Development Setup

For detailed setup instructions, see [LOCAL_SETUP.md](docs/LOCAL_SETUP.md).

### Coding Standards

- **Python**: Follow PEP 8 style guidelines.
- **Formatting**: Use Black for code formatting.
- **Imports**: Use isort for import sorting.
- **Linting**: Use Ruff for linting and fixing issues.
- **Type hints**: Add type annotations where appropriate.

Run the following commands to format and lint your code:

```bash
# Format code
black .

# Sort imports
isort .

# Lint and fix
ruff check . --fix
```

### Testing

- Write unit tests for new functionality.
- Ensure all existing tests pass.
- Run tests with:
  ```bash
  pytest
  ```

### Documentation

- Update documentation for any new features or changes.
- Follow the documentation standards in the `docs/` folder.

### Commit Messages

- Use the present tense ("Add feature" not "Added feature").
- Start with a capital letter.
- Keep the first line under 50 characters.
- Add more detailed description if needed.

### Pull Request Guidelines

- Ensure your PR has a clear title and description.
- Reference any related issues.
- Keep PRs focused on a single feature or fix.
- Be open to feedback and make requested changes.

## Getting Help

If you need help or have questions:
- Check the [documentation](docs/) first.
- Search existing issues and discussions.
- Create a new discussion or issue for questions.

Thank you for contributing to PLOS-backend!