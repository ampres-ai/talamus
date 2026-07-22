# Talamus Memory Privacy Policy

**Effective date:** July 22, 2026

**Publisher:** Angio Crapuzzi, publishing Talamus Memory under the Ampres
open-source project name.

This policy describes data handling by the Talamus Memory plugin and the
Talamus software distributed from the official
[ampres-ai/talamus](https://github.com/ampres-ai/talamus) repository. It does
not replace the privacy terms of OpenAI, GitHub, PyPI, an operating system, or
another service that a user chooses to use with Talamus.

## What the plugin does

Talamus Memory is a skills-only plugin. Installing the plugin adds instructions
that help an agent use a local Talamus command-line installation. Installation
of the plugin itself does not install Talamus, start a server, read local files,
create an account, enable session capture, or call a language model.

The public plugin is intentionally limited to read-only workflows. It can guide
an agent to search and recall local notes, inspect provenance and history,
explore graph relationships, check brain health, and preview a repository scan.
It instructs the agent not to change memory or configuration.

## Data processed locally

When a user runs Talamus, the software may process notes, documents, source
files, citations, and command output selected by that user. The core Talamus
runtime stores its source of truth as local Markdown and uses a rebuildable
local SQLite/FTS5 index. This content is not sent to the publisher, and the
publisher does not operate a hosted Talamus account or memory backend.

Users control the local files and can inspect, edit, back up, or delete them
with their normal filesystem tools. Removing local Talamus files removes them
from the user's machine, subject to backups and operating-system recovery
features controlled by the user.

## Network activity and third parties

The skills-only plugin makes no network request merely because it is installed.
A network request can occur when a user deliberately approves or invokes a
separate operation, including:

- downloading the pinned Talamus package from PyPI through `uvx`;
- using OpenAI products to run the plugin instructions;
- opening the Talamus website, repository, support, or security pages; or
- using optional Talamus features outside this public plugin, such as URL
  ingestion or a user-configured language-model provider.

Those services process data under their own terms and privacy policies. Users
should review the destination before sending private material. The public
Talamus Memory skill tells agents not to expose secrets, use Talamus network or
LLM operations, or ingest URLs.

## Data collected by the publisher

The publisher does not receive or collect a user's prompts, local files, notes,
citations, Talamus brain contents, command output, or credentials through the
plugin. The plugin contains no publisher-operated analytics or telemetry.

If a user chooses to open a GitHub issue, discussion, pull request, or security
report, the publisher receives the information that the user submits there.
Public GitHub posts are visible to others. Users should not include secrets,
private memory, personal data, or credentials in public reports. GitHub
controls storage and retention for information submitted through GitHub.

## Security

The plugin treats retrieved notes, files, URLs, and command output as untrusted
data rather than instructions. It requires explicit consent before a pinned
package download, keeps the published workflow read-only, and tells agents to
avoid secrets and unrelated directories. No software can be guaranteed secure;
users should keep dependencies current and review commands before approval.

Report a suspected vulnerability privately through
[GitHub Security Advisories](https://github.com/ampres-ai/talamus/security/advisories/new).

## Changes and contact

This policy may be updated when Talamus Memory's data practices change. The
effective date above will be updated for material revisions.

For privacy questions, open an issue in the
[Talamus repository](https://github.com/ampres-ai/talamus/issues). Do not include
sensitive information in a public issue.
