# Documentation Update Process

This document outlines the process for keeping documentation up-to-date after any code changes to the AWS Instance Scheduler project.

## 📋 Documentation Update Checklist

### ✅ For Every Code Change

When making any code changes, **ALWAYS** update documentation in this order:

#### 1. Code Documentation (Required)
- [ ] Update function/method docstrings with new parameters
- [ ] Add inline comments for complex logic
- [ ] Update type hints and parameter descriptions
- [ ] Document return value formats and examples

#### 2. Configuration Documentation (If Config Changes)
- [ ] Update `config/config.ini` with new section comments
- [ ] Document new configuration options
- [ ] Provide examples of valid values
- [ ] Explain impact of different settings

#### 3. CLAUDE.md (Primary Developer Documentation)
- [ ] Add new command examples to testing section
- [ ] Update feature lists with new capabilities
- [ ] Add new sections for major features
- [ ] Update version information and feature flags
- [ ] Include GitLab CI usage examples

#### 4. README.md (User-Facing Documentation)
- [ ] Update "Latest Updates" section with new features
- [ ] Add new examples to Quick Start Guide
- [ ] Update feature lists and capabilities
- [ ] Add any new dependencies or requirements
- [ ] Update project status and maturity indicators

#### 5. Help Text and CLI Documentation
- [ ] Update `--help` text for new parameters
- [ ] Ensure parameter descriptions are clear and complete
- [ ] Add usage examples in help text where applicable
- [ ] Test help output to ensure formatting is correct

### 🔄 Documentation Types by Feature Category

#### New Command Line Arguments
- [ ] Update `main.py` argument parser with clear help text
- [ ] Add examples to CLAUDE.md testing section
- [ ] Add examples to README.md Quick Start Guide
- [ ] Update config file with comments if related

#### New Verification/Status Features
- [ ] Document verification levels in code docstrings
- [ ] Add examples showing different verification levels
- [ ] Update config.ini with verification section comments
- [ ] Add troubleshooting section if complex

#### New Dry-Run Features
- [ ] Update dry-run capabilities section in both CLAUDE.md and README.md
- [ ] Add console output examples
- [ ] Document artifact generation and GitLab CI integration
- [ ] Update testing section with new dry-run examples

#### New Target/Filtering Options
- [ ] Document target options in help text
- [ ] Add examples for each target type
- [ ] Update Quick Start Guide with target examples
- [ ] Add to GitLab CI documentation if applicable

### 📝 Documentation Standards

#### Code Docstrings
```python
def example_function(param1, param2='default'):
    """Brief description of what the function does.
    
    Detailed explanation of the function's purpose, behavior, and any
    important implementation details. Include examples if complex.
    
    Args:
        param1 (type): Description of parameter including valid values
        param2 (type, optional): Description with default value noted
        
    Returns:
        type: Description of return value with example structure if complex
        
    Raises:
        ExceptionType: When this exception is raised
        
    Example:
        >>> result = example_function('value1', 'value2')
        >>> print(result)
        {'status': 'success', 'data': [...]}
    """
```

#### Configuration Comments
```ini
[SECTION]
# Brief description of section purpose
# Important: Explain any critical settings

# Parameter description with valid values
parameter_name = default_value

# Complex parameter with detailed explanation
# Options: value1 (description), value2 (description), value3 (description)
# Default: value1 (recommended for most use cases)
# complex_parameter = value1
```

#### Command Examples Format
```bash
# Brief description of what this command does
command --param1 value1 --param2 value2

# More complex example with explanation
command --param1 value1 --param2 value2 --flag    # Comment explaining when to use this
```

### 🚨 Critical Documentation Points

#### Always Document These
1. **Breaking Changes**: Any change that affects existing functionality
2. **New Parameters**: All new command line arguments or config options
3. **Behavioral Changes**: Any change in how existing features work
4. **New Dependencies**: Any new Python packages or system requirements
5. **Version Compatibility**: When features are added or deprecated

#### Documentation Review Process
1. **Self-Review**: Check all documentation before committing
2. **Test Examples**: Verify all command examples actually work
3. **Consistency Check**: Ensure terminology is consistent across all docs
4. **Accessibility**: Ensure examples work for new users following the guide

### 🔧 Automation Reminders

#### After Each Documentation Update
- [ ] Test all command examples in documentation
- [ ] Verify help text displays correctly
- [ ] Check that new features are mentioned in all relevant sections
- [ ] Ensure backward compatibility is maintained and documented

#### Version Release Process
- [ ] Update version numbers in documentation
- [ ] Create changelog entry
- [ ] Update "Latest Updates" sections
- [ ] Verify all examples still work with new version

### 📂 Documentation File Locations

| File | Purpose | Update Frequency |
|------|---------|------------------|
| `CLAUDE.md` | Developer documentation, testing guides | Every change |
| `README.md` | User-facing overview, quick start | Every user-facing change |
| `config/*.ini` | Configuration examples and comments | When config changes |
| `src/main.py` | Help text and argument descriptions | When CLI changes |
| `src/*_operations.py` | Code docstrings and implementation docs | When functions change |
| `test_*.sh` | Executable examples and testing scripts | When workflows change |

### ⚡ Quick Reference

**Before every commit:**
1. Update relevant docstrings
2. Update CLAUDE.md if needed
3. Update README.md if user-facing
4. Test all new examples
5. Verify help text is accurate

**For major features:**
1. Add comprehensive examples
2. Update both CLAUDE.md and README.md
3. Add configuration documentation
4. Create or update test scripts
5. Update version information

---

**Remember**: Good documentation is just as important as good code. Users and future developers rely on accurate, up-to-date documentation to use and maintain the system effectively.

---

## 📝 Recent Major Changes

### v1.4 - Single Account Simplification (EC2 Scheduler)
- **Removed**: Multi-account support (accounts.json file and --accounts parameter)
- **Simplified**: EC2 scheduler now operates on current AWS account credentials only
- **Impact**: Simpler deployment and configuration for single-account environments
- **Documentation Updated**: All examples now include --region parameter and mention single-account operation