-- The fifteen tables Liquibase never created, without which it cannot build a database at all.
--
-- WHY THIS EXISTS
--
-- app_user, tenant, source_job, source_task, storage_connection, notification, scheduler,
-- job_queue, ai_agent and six others are created by NO changeset in this changelog. They exist in
-- every running environment because Hibernate's ddl-auto=update made them once and they have been
-- carried forward ever since. Nothing has ever built this schema from nothing.
--
-- That breaks a fresh database in two different ways:
--
--   dev (ddl-auto=update)     Liquibase runs BEFORE Hibernate in Spring Boot's startup, so V12
--                             tries to add a foreign key to ai_agent and dies with
--                             'relation "ai_agent" does not exist' -- before Hibernate has had
--                             any chance to create it. Reproduced 2026-09-09 against an empty
--                             database, by running the real application image at it.
--
--   stage / prod (validate)   Worse, and silent. Hibernate creates nothing at all, so even with
--                             V12 skipped, fifteen tables would simply never exist. A fresh
--                             production database has never been possible.
--
-- The master changelog's own header already knew half of this: V4-V7 are excluded because they
-- ALTER "tables/columns Hibernate hasn't created yet at Liquibase-run time". V12 has exactly the
-- same problem and was not excluded. Excluding it too would have stopped the crash and left the
-- deeper half -- that the schema does not exist -- exactly where it was.
--
-- WHAT THIS IS, AND WHAT IT IS NOT
--
-- Generated from the live development database with pg_dump --schema-only, because that is the
-- only surviving description of these tables. It is therefore faithful to what is RUNNING; it is
-- not a hand-designed schema, and it inherits whatever ddl-auto=update left behind -- that mode
-- adds columns and never removes or narrows them. The uk_<hash> constraint names below are
-- Hibernate's own and are kept rather than tidied, because renaming them would make this file
-- disagree with every database it is meant to describe.
--
-- Verified by building a database from empty with this in place and starting the application
-- against it under ddl-auto=validate -- the stage and production setting -- which is Hibernate
-- checking this schema against the entity mappings and refusing to start if they disagree.
--
-- Foreign keys are deliberately absent: V12, V13 and V14 are the changesets that add them and
-- they already run after this one. Duplicating them here would give every constraint two owners.
--
-- IDEMPOTENT THROUGHOUT, because this also runs against live databases where all of it already
-- exists. Tables, sequences and indexes use IF NOT EXISTS; PRIMARY KEY and UNIQUE constraints are
-- folded INTO the CREATE TABLE rather than added by ALTER, because PostgreSQL has no
-- ADD CONSTRAINT IF NOT EXISTS and a DO block to work around that would carry semicolons through
-- Liquibase's statement splitter. On an existing database this whole file is a no-op.
--
-- Author: Nabeel Ahmed

CREATE TABLE IF NOT EXISTS public.ai_agent (
    ai_agent_id bigint NOT NULL,
    agent_name character varying(255) NOT NULL,
    api_endpoint character varying(255),
    api_key character varying(1000),
    date_created timestamp without time zone,
    description text,
    instructions text NOT NULL,
    model character varying(255) NOT NULL,
    provider character varying(255) NOT NULL,
    status character varying(255) NOT NULL,
    target_file_types character varying(255) NOT NULL,
    json_mode boolean,
    tool_uuid character varying(36),
    tenant_id bigint,
    created_by bigint,
    updated_by bigint,
    CONSTRAINT ai_agent_pkey PRIMARY KEY (ai_agent_id),
    CONSTRAINT uk_ak9847os2u1gksfnotb3dvtcd UNIQUE (tool_uuid)
);

CREATE TABLE IF NOT EXISTS public.app_user (
    app_user_id bigint NOT NULL,
    date_created timestamp without time zone,
    full_name character varying(255) NOT NULL,
    last_login_at timestamp without time zone,
    password character varying(255) NOT NULL,
    status character varying(255) NOT NULL,
    tenant_id bigint,
    user_role character varying(255) NOT NULL,
    username character varying(255) NOT NULL,
    uuid character varying(36),
    avatar_bucket character varying(255),
    avatar_key character varying(512),
    "position" character varying(120),
    must_change_password boolean DEFAULT false NOT NULL,
    created_by bigint,
    updated_by bigint,
    phone_number character varying(20),
    CONSTRAINT app_user_pkey PRIMARY KEY (app_user_id),
    CONSTRAINT uk_3k4cplvh82srueuttfkwnylq0 UNIQUE (username),
    CONSTRAINT uk_fl8f83s53808r6xtilfaglkb UNIQUE (uuid)
);

CREATE TABLE IF NOT EXISTS public.document_converter_task (
    document_converter_task_id bigint NOT NULL,
    bucket_name character varying(255) NOT NULL,
    date_created timestamp without time zone NOT NULL,
    input_content_type character varying(255),
    input_file_name character varying(255) NOT NULL,
    input_file_size bigint,
    input_format character varying(255) NOT NULL,
    input_storage_key character varying(255) NOT NULL,
    output_content_type character varying(255),
    output_file_name character varying(255),
    output_file_size bigint,
    output_format character varying(255) NOT NULL,
    output_storage_key character varying(255) NOT NULL,
    status character varying(255) NOT NULL,
    task_name character varying(255) NOT NULL,
    tenant_id bigint,
    target_folder character varying(255),
    CONSTRAINT document_converter_task_pkey PRIMARY KEY (document_converter_task_id)
);

CREATE TABLE IF NOT EXISTS public.etl_demo_products (
    sku character varying(64),
    name character varying(255),
    category character varying(128),
    unit_price numeric(12,2),
    in_stock integer
);

CREATE TABLE IF NOT EXISTS public.job_audit_logs (
    job_audit_log_id bigint NOT NULL,
    date_created timestamp without time zone NOT NULL,
    job_queue_id bigint NOT NULL,
    log_detail text NOT NULL,
    status character varying(255) NOT NULL,
    external_id character varying(255),
    CONSTRAINT job_audit_logs_pkey PRIMARY KEY (job_audit_log_id),
    CONSTRAINT uk_dfix0i3vdlmj15gj9fiqae1ge UNIQUE (external_id)
);

CREATE TABLE IF NOT EXISTS public.job_queue (
    job_queue_id bigint NOT NULL,
    date_created timestamp without time zone NOT NULL,
    end_time timestamp without time zone,
    job_id bigint NOT NULL,
    job_send boolean,
    job_status character varying(255) NOT NULL,
    job_status_message text,
    run_manual boolean,
    skip_manual boolean,
    skip_time timestamp without time zone,
    start_time timestamp without time zone,
    status character varying(255) NOT NULL,
    bucket character varying(255),
    output_folder character varying(255),
    CONSTRAINT job_queue_pkey PRIMARY KEY (job_queue_id)
);

CREATE TABLE IF NOT EXISTS public.kafka_connection_profile (
    kafka_connection_profile_id bigint NOT NULL,
    bootstrap_servers text NOT NULL,
    is_default boolean NOT NULL,
    date_created timestamp without time zone,
    profile_name character varying(255) NOT NULL,
    sasl_mechanism character varying(255),
    sasl_password character varying(1000),
    sasl_username character varying(255),
    security_protocol character varying(255) NOT NULL,
    status character varying(255) NOT NULL,
    additional_properties text,
    environment_label character varying(255),
    last_test_message text,
    last_tested_at timestamp without time zone,
    ssl_endpoint_identification_algorithm character varying(255),
    ssl_key_password_enc character varying(1000),
    ssl_keystore_location character varying(255),
    ssl_keystore_password_enc character varying(1000),
    ssl_truststore_location character varying(255),
    ssl_truststore_password_enc character varying(1000),
    tenant_id bigint,
    connection_status character varying(255),
    ssl_keystore_bucket character varying(255),
    ssl_truststore_bucket character varying(255),
    created_by bigint,
    updated_by bigint,
    CONSTRAINT kafka_connection_profile_pkey PRIMARY KEY (kafka_connection_profile_id)
);

CREATE TABLE IF NOT EXISTS public.notification (
    notification_id bigint NOT NULL,
    date_created timestamp without time zone NOT NULL,
    link_url character varying(255),
    message character varying(2000),
    is_read boolean NOT NULL,
    read_at timestamp without time zone,
    recipient_user_id bigint NOT NULL,
    severity character varying(255) NOT NULL,
    tenant_id bigint,
    title character varying(255) NOT NULL,
    type character varying(255) NOT NULL,
    CONSTRAINT notification_pkey PRIMARY KEY (notification_id)
);

CREATE TABLE IF NOT EXISTS public.scheduler (
    scheduler_id bigint NOT NULL,
    date_created timestamp without time zone,
    end_date date,
    frequency character varying(255) NOT NULL,
    job_id bigint NOT NULL,
    interval_value character varying(255),
    start_date date NOT NULL,
    start_time time without time zone NOT NULL,
    days_of_week character varying(30),
    day_of_month smallint,
    next_run_at timestamp without time zone,
    expired boolean DEFAULT false NOT NULL,
    date_updated timestamp without time zone,
    CONSTRAINT scheduler_pkey PRIMARY KEY (scheduler_id)
);

CREATE TABLE IF NOT EXISTS public.source_job (
    job_id bigint NOT NULL,
    complete_job boolean,
    date_created timestamp without time zone NOT NULL,
    execution character varying(255) NOT NULL,
    fail_job boolean,
    job_name character varying(1000) NOT NULL,
    job_running_status character varying(255),
    job_status character varying(255) NOT NULL,
    last_job_run timestamp without time zone,
    priority integer NOT NULL,
    skip_job boolean,
    task_detail_id bigint,
    tenant_id bigint,
    assigned_user_id bigint,
    created_by bigint,
    updated_by bigint,
    CONSTRAINT source_job_pkey PRIMARY KEY (job_id)
);

CREATE TABLE IF NOT EXISTS public.source_task (
    task_detail_id bigint NOT NULL,
    home_page_id character varying(255),
    pipeline_id character varying(255),
    task_name character varying(255) NOT NULL,
    task_payload text,
    task_status character varying(255) NOT NULL,
    source_task_type_id bigint,
    tenant_id bigint,
    group_id character varying(255),
    bucket character varying(255),
    input_folder character varying(255),
    output_folder character varying(255),
    created_by bigint,
    updated_by bigint,
    CONSTRAINT source_task_pkey PRIMARY KEY (task_detail_id)
);

CREATE TABLE IF NOT EXISTS public.source_task_payload (
    task_payload_id bigint NOT NULL,
    tag_key character varying(255),
    tag_parent character varying(255),
    tag_value text,
    payload_id bigint,
    CONSTRAINT source_task_payload_pkey PRIMARY KEY (task_payload_id)
);

CREATE TABLE IF NOT EXISTS public.storage_connection (
    storage_connection_id bigint NOT NULL,
    access_key character varying(255),
    alias character varying(255) NOT NULL,
    azure_account_name character varying(255),
    azure_connection_string_enc character varying(2000),
    base_directory character varying(255),
    bucket_name character varying(255),
    connection_name character varying(255) NOT NULL,
    connection_status character varying(255),
    date_created timestamp without time zone,
    description character varying(255),
    endpoint character varying(255),
    host character varying(255),
    implicit_tls boolean,
    is_default boolean NOT NULL,
    last_test_message text,
    last_tested_at timestamp without time zone,
    passive_mode boolean,
    password_enc character varying(1000),
    port integer,
    provider character varying(255) NOT NULL,
    region character varying(255),
    secret_key_enc character varying(1000),
    status character varying(255) NOT NULL,
    tenant_id bigint,
    username character varying(255),
    created_by bigint,
    updated_by bigint,
    CONSTRAINT storage_connection_pkey PRIMARY KEY (storage_connection_id),
    CONSTRAINT uq_storage_connection_alias UNIQUE (alias)
);

CREATE TABLE IF NOT EXISTS public.tenant (
    tenant_id bigint NOT NULL,
    date_created timestamp without time zone,
    status character varying(255) NOT NULL,
    tenant_code character varying(255) NOT NULL,
    tenant_name character varying(255) NOT NULL,
    uuid character varying(36),
    created_by bigint,
    updated_by bigint,
    CONSTRAINT tenant_pkey PRIMARY KEY (tenant_id),
    CONSTRAINT uk_4dwx7sonk7tq4x03en9377rou UNIQUE (uuid),
    CONSTRAINT uk_ng2jtiduv4m34nlcypgqdp29j UNIQUE (tenant_code)
);

CREATE TABLE IF NOT EXISTS public.tenant_task_type_kafka_route (
    tenant_task_type_kafka_route_id bigint NOT NULL,
    date_created timestamp without time zone,
    kafka_connection_profile_id bigint NOT NULL,
    source_task_type_id bigint NOT NULL,
    tenant_id bigint NOT NULL,
    CONSTRAINT tenant_task_type_kafka_route_pkey PRIMARY KEY (tenant_task_type_kafka_route_id),
    CONSTRAINT uq_tenant_task_type UNIQUE (tenant_id, source_task_type_id)
);

CREATE SEQUENCE IF NOT EXISTS public.notification_notification_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.notification_notification_id_seq OWNED BY public.notification.notification_id;

ALTER TABLE ONLY public.notification ALTER COLUMN notification_id SET DEFAULT nextval('public.notification_notification_id_seq'::regclass);

CREATE INDEX IF NOT EXISTS idx_ai_agent_tenant_id ON public.ai_agent USING btree (tenant_id);

CREATE INDEX IF NOT EXISTS idx_app_user_tenant_id ON public.app_user USING btree (tenant_id);

CREATE INDEX IF NOT EXISTS idx_document_converter_task_tenant_id ON public.document_converter_task USING btree (tenant_id);

CREATE INDEX IF NOT EXISTS idx_job_audit_logs_job_queue_id ON public.job_audit_logs USING btree (job_queue_id);

CREATE INDEX IF NOT EXISTS idx_job_queue_job_id ON public.job_queue USING btree (job_id);

CREATE INDEX IF NOT EXISTS idx_kcp_tenant_id ON public.kafka_connection_profile USING btree (tenant_id);

CREATE INDEX IF NOT EXISTS idx_notification_recipient ON public.notification USING btree (recipient_user_id);

CREATE INDEX IF NOT EXISTS idx_notification_recipient_read ON public.notification USING btree (recipient_user_id, is_read);

CREATE INDEX IF NOT EXISTS idx_notification_tenant_id ON public.notification USING btree (tenant_id);

CREATE INDEX IF NOT EXISTS idx_scheduler_job_id ON public.scheduler USING btree (job_id);

CREATE INDEX IF NOT EXISTS idx_scheduler_next_run_at ON public.scheduler USING btree (next_run_at);

CREATE INDEX IF NOT EXISTS idx_source_job_assigned_user_id ON public.source_job USING btree (assigned_user_id);

CREATE INDEX IF NOT EXISTS idx_source_job_task_detail_id ON public.source_job USING btree (task_detail_id);

CREATE INDEX IF NOT EXISTS idx_source_job_tenant_id ON public.source_job USING btree (tenant_id);

CREATE INDEX IF NOT EXISTS idx_source_task_payload_task ON public.source_task_payload USING btree (payload_id);

CREATE INDEX IF NOT EXISTS idx_source_task_tenant_id ON public.source_task USING btree (tenant_id);

CREATE INDEX IF NOT EXISTS idx_source_task_type_id ON public.source_task USING btree (source_task_type_id);

CREATE INDEX IF NOT EXISTS idx_storage_connection_tenant_id ON public.storage_connection USING btree (tenant_id);

CREATE INDEX IF NOT EXISTS idx_ttkr_profile_id ON public.tenant_task_type_kafka_route USING btree (kafka_connection_profile_id);

CREATE INDEX IF NOT EXISTS idx_ttkr_task_type_id ON public.tenant_task_type_kafka_route USING btree (source_task_type_id);

CREATE INDEX IF NOT EXISTS idx_ttkr_tenant_id ON public.tenant_task_type_kafka_route USING btree (tenant_id);
