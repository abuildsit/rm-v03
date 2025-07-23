Please analyze the pull request based on the Github PR: $ARGUMENTS,

Follow these steps.

# Overview:
- You work with a team of clumsy engineers who frequently fail to grasp the interplay between different parts of the codebase. As such, consider this during execution.
- The design goal is for simple, efficient code - avoiding needlessly complicated architecture

# ANALYZE
1. Use 'gh pr view' to get the PR details and diff
2. Understand the changes made in the PR
3. Check the original issue context if linked
4. Review the code quality and architecture decisions
   - Search the codebase for similar patterns and implementations
   - Check for consistency with existing code style
   - Look for potential breaking changes or side effects
   - Review relevant project documentation in ./docs/structure.


# ASSESS
5. Evaluate the PR against these criteria:
   - Code quality and readability
   - Security vulnerabilities
   - Performance implications
   - Test coverage
   - Documentation updates
   - Breaking changes
   - Adherence to team conventions

# FEEDBACK
6. Provide structured feedback:
   - Highlight positive aspects
   - Identify critical issues that must be fixed
   - Suggest improvements for code quality
   - Point out potential edge cases or bugs
   - Recommend additional tests if needed

# DECISION
7. Make a review recommendation:
   - APPROVE: Ready to merge
   - REQUEST_CHANGES: Critical issues need fixing
   - COMMENT: Suggestions but not blocking

# DOCUMENT
8. Update Documentation including:
    - If Approving, close the github issue if appropriate.
    - Confirm updates have occurred in relevant documents in ./docs/structure if required.

Remember to use the GitHub CLI ('gh') for all GitHub-related tasks