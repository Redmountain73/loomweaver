Agent Name: Loomweaver Mentor

Agent Purpose and Identity:

1. Teach others to write Loom modules.
2. Speak in a patient, schema-obsessed but friendly tone.

I. Greeting Module
A. Purpose and Identity

1. Generate a friendly greeting.
2. Maintain warmth and clarity.

B. Inputs

1. name (Text)

C. Outputs

1. message (Text)

D. Flow

1. make message say the user’s name
2. if the user has no name then return "anonymous user"
3. otherwise return message

E. Tests

1. Input: Alice → Output: "Hello, Alice!"
2. Input: (no name) → Output: "anonymous user"

F. Success Criteria (What Good Looks Like)

1. Always return a greeting string.
2. Never fail silently.

G. Version: 1.0
H. astVersion: 2.1.0

I. Examples (Optional)

1. Example dialogue: User: "hi" → Output: "Hello, hi!"

II. Score Gate Module
A. Purpose and Identity

1. Evaluate a numeric score.
2. Produce a simple pass/fail verdict.

B. Inputs

1. score (Number)

C. Outputs

1. verdict (Text)

D. Flow

1. if score is at least 90 then return "pass"
2. otherwise return "fail"

E. Tests

1. Input: 95 → Output: "pass"
2. Input: 42 → Output: "fail"

F. Success Criteria (What Good Looks Like)

1. Numeric comparison uses thresholds as written.
2. Output is always one of: "pass", "fail".

G. Version: 1.0
H. astVersion: 2.1.0

III. Echo Module
A. Purpose and Identity

1. Echo back a provided name.
2. Stay minimal and deterministic.

B. Inputs

1. name (Text)

C. Outputs

1. echo (Text)

D. Flow

1. make echo say name, then return echo

E. Tests

1. Input: Bob → Output: "Bob"

## Agent (top-level)
Agent Name
ArxivAgent

A. Purpose and Identity
   1. A demo agent that queries arXiv for papers and returns a formatted summary.

B. Inputs
   1. query

B. Outputs
   1. report

C. Flow
   1. Call "Arxiv Search" with query=query, then get xml
   2. Call "Summarize Title" with xml=xml, then get title
   3. Make report = "Found paper: " + title
   4. Show report
   5. Return report

D. Tests
   1. query="all:graph" then result contains "Found paper:"

E. Success Criteria
   1. Returns a readable one-line report.

F. Examples
   1. query: "all:graph neural networks"

G. Version
   0.2.0

H. astVersion
   0.1.0

## Module (within agent)
I. Module Name
Arxiv Search
A. Purpose and Identity
   1. Fetch arXiv metadata
B. Inputs
   1. query
C. Outputs
   1. xml
   2. status
   3. bytes
D. Flow
   1. Fetch "https://export.arxiv.org/api/query?search_query={query}&max_results=1"
      into=xml, intoStatus=status, intoBytes=bytes
   2. Return xml
E. Tests
   1. input: query="all:graph" expect: contains "entry"
F. Success Criteria
   1. xml contains <entry>
G. Examples
   1. query: "all:graph"
H. Version
   0.2.0
I. astVersion
   0.1.0
