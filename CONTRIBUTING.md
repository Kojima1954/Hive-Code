# Contributing to Conversational Swarm Intelligence Network

Thank you for your interest in contributing to the Swarm Network project! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what's best for the community
- Show empathy towards other community members

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in Issues
2. If not, create a new issue with:
   - Clear, descriptive title
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, etc.)
   - Relevant logs or screenshots

### Suggesting Enhancements

1. Check if the enhancement has been suggested
2. Create a new issue with:
   - Clear description of the enhancement
   - Use cases and benefits
   - Possible implementation approach
   - Any relevant examples

### Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Update documentation
7. Commit your changes (`git commit -m 'Add amazing feature'`)
8. Push to your fork (`git push origin feature/amazing-feature`)
9. Open a Pull Request

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/Hive-Code.git
cd Hive-Code

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install black flake8 mypy pytest-cov

# Copy environment file
cp .env.example .env
```

## Coding Standards

### Python Style

- Follow PEP 8
- Use type hints for all functions
- Write docstrings for all classes and functions
- Maximum line length: 100 characters

```python
def example_function(param: str, count: int = 0) -> dict:
    """
    Brief description of function.
    
    Args:
        param: Description of param
        count: Description of count
        
    Returns:
        Description of return value
    """
    pass
```

### Code Formatting

```bash
# Format code with Black
black core/ ui/ tests/

# Check style with flake8
flake8 core/ ui/ tests/

# Type checking with mypy
mypy core/ ui/
```

### Testing

- Write unit tests for all new features
- Maintain or improve code coverage
- Use pytest for testing
- Mark tests appropriately (unit, integration, slow)

```python
import pytest

@pytest.mark.unit
async def test_new_feature():
    """Test description."""
    # Arrange
    # Act
    # Assert
    pass
```

### Documentation

- Update README.md for user-facing changes
- Update USAGE.md for new features
- Add docstrings to all public APIs
- Include code examples where appropriate

## Project Structure

```
core/               # Core business logic
├── node/          # Node management
├── memory/        # Memory system
├── federation/    # Federation/ActivityPub
├── security/      # Security features
└── monitoring/    # Metrics and logging

ui/                # User interface
├── web/          # Web application
└── api/          # API definitions

tests/             # Test suite
deployment/        # Deployment configs
scripts/           # Utility scripts
```

## Testing Guidelines

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_node_manager.py -v

# With coverage
pytest tests/ --cov=core --cov=ui --cov-report=html

# Only unit tests
pytest tests/ -v -m unit

# Only integration tests (requires Redis)
pytest tests/ -v -m integration
```

### Writing Tests

1. **Arrange-Act-Assert Pattern**
   ```python
   async def test_add_participant(node):
       # Arrange
       user_id = "test_user"
       
       # Act
       participant = await node.add_human_participant(user_id, "Test")
       
       # Assert
       assert participant.id == user_id
   ```

2. **Use Fixtures**
   ```python
   @pytest.fixture
   async def memory_manager():
       manager = DiffMemManager(storage_path="/tmp/test")
       yield manager
       # Cleanup
   ```

3. **Mock External Services**
   ```python
   @pytest.fixture
   def mock_ollama(monkeypatch):
       def mock_chat(*args, **kwargs):
           return {"message": {"content": "Mock response"}}
       monkeypatch.setattr("ollama.Client.chat", mock_chat)
   ```

## Commit Guidelines

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples

```
feat(node): add support for custom AI models

- Allow users to specify custom Ollama models
- Add model validation
- Update documentation

Closes #123
```

```
fix(security): resolve rate limiting bypass issue

The rate limiter was not properly handling concurrent requests.
Added proper locking mechanism using Redis.

Fixes #456
```

## Review Process

### What We Look For

1. **Functionality**
   - Does it work as intended?
   - Are edge cases handled?
   - Is error handling appropriate?

2. **Code Quality**
   - Follows coding standards
   - Well-documented
   - Appropriate test coverage
   - No unnecessary complexity

3. **Performance**
   - No performance regressions
   - Efficient algorithms
   - Proper async/await usage

4. **Security**
   - No security vulnerabilities
   - Proper input validation
   - Safe handling of sensitive data

### Review Timeline

- Initial review: Within 3-5 days
- Follow-up reviews: Within 2 days
- Merging: After approval from maintainers

## Feature Development Workflow

1. **Discuss**: Open an issue to discuss the feature
2. **Design**: Agree on design and approach
3. **Implement**: Create PR with implementation
4. **Review**: Address review feedback
5. **Test**: Ensure all tests pass
6. **Document**: Update documentation
7. **Merge**: Maintainer merges the PR

## Areas for Contribution

### High Priority

- [ ] Additional AI model integrations
- [ ] Enhanced memory clustering algorithms
- [ ] Performance optimizations
- [ ] Additional test coverage
- [ ] Documentation improvements

### Medium Priority

- [ ] UI/UX enhancements
- [ ] Additional federation features
- [ ] Monitoring dashboards
- [ ] CLI tools
- [ ] Migration scripts

### Good First Issues

Look for issues labeled `good-first-issue` for beginner-friendly contributions.

## Questions?

- Open a discussion on GitHub
- Check existing issues and PRs
- Review the documentation

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT License).

## Recognition

Contributors will be recognized in:
- README.md contributors section
- Release notes for significant contributions
- GitHub's contributor graph

Thank you for making Swarm Network better! 🐝
