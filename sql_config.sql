CREATE TABLE IF NOT EXISTS trophies
(
    id   VARCHAR(32) PRIMARY KEY,
    name VARCHAR(64) NOT NULL
);

CREATE TABLE IF NOT EXISTS users
(
    id           BIGINT PRIMARY KEY,
    points       INT DEFAULT 0 CHECK ( points >= 0 ),
    total_events INT DEFAULT 0,
    won_events   INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS inventories
(
    id          BIGINT      NOT NULL REFERENCES users ON DELETE CASCADE,
    trophy_id   VARCHAR(32) NOT NULL REFERENCES trophies ON DELETE CASCADE,
    obtained_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id, trophy_id)
);

CREATE TABLE IF NOT EXISTS nitro_shop
(
    name      VARCHAR(64)  NOT NULL,
    price     INT          NOT NULL,
    gift_link VARCHAR(128) NOT NULL
);

CREATE TABLE IF NOT EXISTS events
(
    id                      UUID PRIMARY KEY,
    name                    VARCHAR(16) NOT NULL,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    registration_channel_id BIGINT      NOT NULL,
    registration_message_id BIGINT      NOT NULL
);

CREATE TABLE IF NOT EXISTS groups
(
    event_id   UUID REFERENCES events ON DELETE CASCADE NOT NULL,
    start_time TIMESTAMP                                NOT NULL,
    role_id    BIGINT                                   NOT NULL,
    closed     BOOLEAN DEFAULT FALSE,
    UNIQUE (event_id, role_id)
);

CREATE TABLE IF NOT EXISTS version_data
(
    id      SMALLINT UNIQUE DEFAULT 0,
    version SMALLINT NOT NULL
);

INSERT INTO version_data (id, version)
VALUES (0, 1)
ON CONFLICT DO NOTHING;
