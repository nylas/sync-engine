Goals
=====

To explore restructuring the sync database to create a separate
datastore for use by the API, with a denormalised schema optimised for
API use cases.

We expect the benefits of this design to include:

-   lower API latency due to optimised schema
-   better scalability through ability to tune sync and API schemas
    independently
-   more predictable and consistent sync behaviour through eliminating
    competing writes to the sync database
-   paves the way to add more use cases that depend on synced data
    without impacting sync codebase

Design
======

[Architecture
diagram](https://www.dropbox.com/s/c77axsvpc9t068t/data-flow_api-store-patch.jpg?dl=0)

We decided to use MySQL for the API data store, after some prototyping.
The reasoning for this is discussed further in the Learnings section
below. The basic design is essentially to treat MySQL as a "NoSQL"
document store with secondary indexes. (WiX Engineering wrote a report
on their [similar
architecture](http://blog.wix.engineering/2015/12/10/scaling-to-100m-mysql-is-a-better-nosql/).)

We eagerly precompute the JSON representations (as served by the API)
for all objects at the time they are created or modified, and store that
JSON as a single blob column for immediate retrieval and serving, keyed
by object id. Since some objects have more than one representation (e.g.
`view=expanded`), we precompute and store all representations, each in
its own column. This provides semantics similar to a "NoSQL" document
store, and provides key-value access - e.g. `GET /messages/:id`.

Since the API also supports bulk queries (e.g. `GET /messages`) with a
default ordering (by date), and various filtering options (e.g.
`GET /messages?subject=Status+update`), we augment the JSON records with
additional columns to serve as secondary indexes.

This is a denormalised schema, since the same information is duplicated
between several columns (multiple JSON representations, plus the values
in the secondary index columns are also present in the JSON) - not to
mention the fact that all this information is still presently stored, in
a more normalised form, in the sync database. (See Future Directions
section below for more on this latter point.)

The schema for the API store consists of one table per API object type -
e.g. message, thread. For example the `apithread` table contains the
following columns (excerpted for clarity):

-   `id (BigInteger)` - internal id of the object in sync DB
-   `public_id (BINARY(16))` - `public_id` of the object in sync DB
-   `value (LONGBLOB)` - JSON representation of the object, as served by
    the API
-   `expanded_value (LONGBLOB)` - for objects supporting `view=expanded`
-   `recentdate (DateTime)` - to support retrieving threads in date
    order
-   `subject (String)` - secondary index column to support filtering by
    subject
-   ... other secondary index columns (from\_addrs, to\_addrs, etc)

### Populating the API store

The API store is populated by subscribing to a feed of changes emitted
by the sync process. This is currently implemented by an after\_flush
hook in the sync service, relying on the existing transaction log.

This keeps the API store up to date as mailboxes change. In addition, we
need to bootstrap the initial contents of the store. We use a script
that bootstraps a single account by paging through the existing sync DB
tables and creating the corresponding API store records.

### Optimistic updates

The API includes mutation operations such as starring a message
(`PUT /messages/:id {"starred": true}`), and API users reasonably expect
to "read their own writes" - if they star a message and then quickly
re-request that same message, they expect to see it starred.

However, it may take some time until the change has been persisted in
the upstream mail provider and synced back into the sync DB. To remain
consistent with the *API user's* view of the message, the API needs to
become temporarily *inconsistent* with *upstream's* view of the message.

To cover this case, the API has historically updated the sync DB
directly to reflect the change. In the "happy path" this is fine, but it
can cause problems if the syncback action persistently fails, or if
there are any bugs in the API code - since the old state of the object
is lost, the sync DB is now *permanently* inconsistent with upstream.
This can also occur in situations where the API's optimistic update does
not completely reproduce the semantics of the upstream operation, as has
happened previously with Gmail's "folder-like label" semantics.

In this design, since the API is reading from a separate data store,
there is no need for it to ever modify the sync DB. Instead, we give it
a separate "patch store" to store its optimistic updates. API queries
then read from both the patch store and the main API store. When the
syncback action has completed, we delete the patch.

The patch store has a similar schema to the main API store - a table for
each type of object, with JSON values keyed by id. However the patch
store does not require secondary indices, since it is never bulk-queried
directly.

The advantage of this design is that there is a clear separation of
concerns and ownership between the three stores:

-   the sync DB is written to only by the sync process (and syncback),
    and represents our best-effort replica of the upstream provider
    (best-effort in that bugs or failures in sync can of course result
    in inconsistency).
-   the API store is written to only as a result of updates to the sync
    DB, and represents a replica of the sync DB, transformed into the
    API-optimised schema.
-   the patch store is written to only by the API, and by syncback
    actions completing. It represents any temporary modifications made
    to emulate the result of pending syncback actions. Any inconsistency
    as a result of this emulation is therefore isolated to the patch
    store.

Status
======

We have developed a working prototype of the design by branching the
existing `sync-engine` codebase.

### State of prototype

Because of the large surface area of the API and supported operations,
object types, and filtering options, the prototype does not implement
the complete API. It supports GET and PUT on messages and threads (the
GET operations are exposed on separate endpoints `/messages2` and
`/threads2` to aid comparing the results of the new implementation with
the existing). The bootstrap script currently bootstraps only messages,
but not threads. Not all filtering options are supported.

Some of the unit tests have been extended to run against the new
implementation as well as the existing one. However not 100% of the
tests pass currently.

### Missing pieces

-   Needs review for correct sharding behaviour
-   Does not correctly distinguish between messages and drafts
-   Mutating a message will not patch the corresponding thread, and vice
    versa, so e.g. starring a message then reading the thread may
    briefly see the thread as unstarred
-   Currently there is a brief window between clearing a patch (when the
    syncback action completes) and the update syncing down from
    upstream, when the client can read the old value (before
    modification) again. See [sequence
    diagram](https://www.dropbox.com/s/t709q5x33t3tous/sequence_race-condition-patch.png?dl=0).
    This should be resolvable once syncback is integrated with sync, by
    instead clearing the patch when the next sync update arrives,
    instead of as soon as the syncback action completes.
-   Filtering by multi-valued fields (e.g. from\_addrs) is implemented
    very inefficiently: field is persisted as a JSON array and queried
    via LIKE, without an index. Should be possible to extract the values
    into their own table and query across the join - e.g.
    `SELECT * FROM apimessage WHERE id IN (SELECT obj_id FROM   apifrom_addr WHERE from_addr = 'test@example.com')`
-   The delta API is not currently aware of writes to the patch store,
    and therefore an optimistic update will not generate a new delta.
    Clients using both mutation operations and the delta API may
    therefore briefly see inconsistent results. (Assuming the syncback
    action succeeds, they will eventually see a delta once the result
    syncs from upstream.) To resolve this, we would need to move the
    delta logic into the API store, instead of generating it directly
    from the transaction log.

Evaluation and learnings
========================

### Feasibility

The prototype shows that implementing this design is feasible. The code
changes are substantial, but not very intrusive. If desired it should be
feasible to run the new implementation in parallel with the existing
(e.g. enabling it only for certain accounts).

### Time and space

Some limited benchmarking was carried out, using a single large account
(200k messages). In terms of space usage, with MySQL row compression
enabled, the new implementation required about 3x the disk space of the
existing implementation - this is a promising result given that the
denormalised schema is expected to be space-hungry. In terms of
performance, we observed around 50% lower latency for a
`GET /messages?subject=x` bulk query. More extensive benchmarking is
recommended but early results are promising.

### Database technology

For the prototype we considered: Redis, MySQL, Postgres, RethinkDB

Considerations include:

-   Large storage requirements due to the denormalised schema (trading
    space for time). This makes in-memory stores like Redis infeasible.
    It is also preferable if the data store supports on-disk compression
    of stored values, since JSON compresses very effectively. MySQL
    supports this via
    [ROW\_FORMAT=COMPRESSED](https://dev.mysql.com/doc/refman/5.6/en/innodb-compression-background.html).
-   Filtering, sorting etc require secondary index support.
-   Recent versions of Postgres support indexing on fields *within* a
    value stored as a JSON blob; this could simplify the design,
    avoiding the need for creating separate columns to sort and filter
    by.
-   The team has extensive experience with MySQL, both in development
    and operations.

### Maintainability

This design creates a clearer separation of responsibility between the
sync system and the API, since they no longer share a data store. They
interact only via the transaction log, the action log, and syncback
clearing patches.

That should point the way to simplifying both systems, and allowing each
to be developed and tested in isolation from the other.

Future/Alternative Directions
=============================

### Kafka

The API store is essentially a derived data store based on the sync DB.
Maintaining a derived data store can be operationally complex in the
case that you need to change the way the data is derived - e.g. to add a
new secondary index, or after fixing a bug in the logic that populates
the API store. This may require repopulating some or all of the records
in the API store.

These operations can be made much simpler by using Kafka as the change
feed that the API store subscribes to (rather than hooking directly into
the transaction log). By publishing all sync updates to a Kafka topic,
Kafka can be configured to persist these updates. Then the API store
builder consumes these updates and populates the API store. The store
can be bootstrapped by consuming from offset zero in this topic, and
stay up to date by consuming from the end of the topic.

Should the logic for populating the store need to change, it is then
straightforward to regenerate the store by reconsuming from offset 0.

Having the sync updates in a Kafka topic also makes it trivial to hang
other consumers off the same topic, so that other use cases can also
depend on synced data. For example a sophisticated search system could
be built without changes to the sync system.

### Simplifying sync store

Now that sync and API use separate stores, it may make sense to simplify
the sync DB considerably. In the current prototype, it still contains a
well-normalised schema representing messages, threads, recipients etc,
but none of that is required for the actual mail sync process. It might
be possible to emit raw message bodies into the sync stream (whether
in-process as in the current prototype, or in Kafka), and move all
message parsing into the API logic, then simply stop storing message
details in the sync DB.

That would allow significant tuning of the sync DB (e.g. removing many
indexes). It would also move complex logic, such as dealing with label
semantics, out of the sync DB, and allow it to be tested in isolation.
