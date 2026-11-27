# Glossary

- **Event**: one JSON object with an `event_type` and an `event_payload`.
- **Valid Event**: an Event whose `event_type` and `event_payload` are both strings, with no other fields.
- **Events File**: the JSON array of predefined Events that the Propagator chooses from.
- **Propagator**: the service that sends a randomly chosen Event from the Events File every Interval.
- **Interval**: the number of seconds between two sends.
- **Consumer**: the service that receives Events on `/event` and stores Valid Events.
- **Stored Event**: a Valid Event plus the time the Consumer received it.
- **Rate Limit**: the global cap on `/event` requests the Consumer accepts, set as requests per second with a burst; requests over it get `429` and are not stored.
