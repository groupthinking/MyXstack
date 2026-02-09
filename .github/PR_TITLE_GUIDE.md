# PR Title Quick Reference

## Conventional Commits Format

All PR titles should follow the [Conventional Commits](https://www.conventionalcommits.org/) format:

**Format**: `<type>(<scope>): <description>`

### Types and Examples

| Type | When to Use | Example |
|------|-------------|---------|
| `feat` | New feature | `feat(agent): add autonomous reply functionality` |
| `fix` | Bug fix | `fix(xapi): correct mention polling interval` |
| `docs` | Documentation only | `docs: update README.md and simplify xAI instructions` |
| `refactor` | Code restructuring | `refactor(grok): simplify AI decision logic` |
| `chore` | Maintenance | `chore: update dependencies to latest versions` |
| `ci` | CI/CD changes | `ci: add PR validation workflow` |
| `style` | Formatting changes | `style: fix indentation in config files` |
| `test` | Test updates | `test: add unit tests for agent service` |
| `perf` | Performance improvements | `perf(xapi): optimize mention polling` |

### How to Update PR Title

1. Go to your PR page on GitHub
2. Click the "Edit" button next to the PR title
3. Update the title to follow the format above
4. Save changes

The PR validation workflow will then pass with no warnings.

## Common Scenarios

### Documentation Updates
**Problem**: PR title like "updates to the `README.md`"  
**Solution**: `docs: update README.md and simplify xAI instructions`

### Multiple File Changes
**Problem**: PR title like "various fixes"  
**Solution**: Choose the primary change type:
- `fix: resolve polling and authentication issues`
- `refactor: restructure API client and services`

### Feature Additions
**Problem**: PR title like "new stuff"  
**Solution**: `feat(agent): implement autonomous decision-making`

## Full Guidelines

For comprehensive contribution guidelines, see [CONTRIBUTING.md](/CONTRIBUTING.md).

---

**Note**: The PR validation workflow treats conventional commits format as a **warning** (not an error), so PRs will not be blocked. However, following this format improves project maintainability and changelog generation.
