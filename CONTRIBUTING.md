# Contributing to MyXstack

Thank you for contributing to MyXstack! This guide will help you understand our contribution process and conventions.

## Pull Request Guidelines

### PR Title Format

We follow the [Conventional Commits](https://www.conventionalcommits.org/) format for PR titles. This helps us automatically generate changelogs and understand the nature of changes at a glance.

**Format**: `<type>(<scope>): <description>`

**Types**:
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation changes only
- `style`: Code style changes (formatting, semicolons, etc.) that don't affect functionality
- `refactor`: Code changes that neither fix bugs nor add features
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `chore`: Maintenance tasks, dependency updates
- `ci`: Changes to CI/CD configuration
- `build`: Changes to build system or dependencies
- `revert`: Reverting a previous commit

**Scope** (optional): The area of the codebase affected (e.g., `agent`, `xapi`, `grok`, `mcp`)

**Examples**:
- `docs: update README.md and simplify xAI instructions`
- `feat(agent): add autonomous reply functionality`
- `fix(xapi): correct mention polling interval`
- `chore: update dependencies to latest versions`
- `ci: add PR validation workflow`

### PR Description

- Provide a clear description of what the PR does (minimum 20 characters)
- Reference related issues using `#issue-number`
- Explain the motivation for the change
- List any breaking changes
- Include testing steps if applicable

### PR Size

- Try to keep PRs focused and under 500 lines of changes
- Large PRs (>500 lines) will trigger a warning
- Consider breaking large changes into smaller, reviewable chunks
- If a large PR is unavoidable, provide extra context in the description

## Code Style

Follow the guidelines in `.github/copilot-instructions.md`:
- Use TypeScript strict mode
- Prefer async/await over raw promises
- Always wrap API calls in try-catch blocks
- Use explicit types; avoid `any`
- Follow naming conventions:
  - Classes: PascalCase (e.g., `XAPIClient`)
  - Functions: camelCase (e.g., `fetchMentions`)
  - Constants: UPPER_SNAKE_CASE (e.g., `DEFAULT_POLLING_INTERVAL`)

## Testing

- Run `npm run build` to verify TypeScript compilation
- Test changes in simulation mode when possible
- Ensure existing tests pass before submitting

## Questions?

If you have questions, feel free to:
- Open an issue for discussion
- Ask in your PR comments
- Check the existing documentation in `ARCHITECTURE.md` or `USAGE.md`
