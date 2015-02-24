-- MySQL dump 10.13  Distrib 5.5.40, for debian-linux-gnu (x86_64)
--
-- Host: localhost    Database: inbox
-- ------------------------------------------------------
-- Server version	5.5.40-0ubuntu0.12.04.1-log

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `account`
--

DROP TABLE IF EXISTS `account`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `account` (
  `public_id` binary(16) NOT NULL,
  `_raw_address` varchar(191) DEFAULT NULL,
  `_canonicalized_address` varchar(191) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `save_raw_messages` tinyint(1) DEFAULT '1',
  `last_synced_contacts` datetime DEFAULT NULL,
  `inbox_folder_id` int(11) DEFAULT NULL,
  `sent_folder_id` int(11) DEFAULT NULL,
  `drafts_folder_id` int(11) DEFAULT NULL,
  `spam_folder_id` int(11) DEFAULT NULL,
  `trash_folder_id` int(11) DEFAULT NULL,
  `archive_folder_id` int(11) DEFAULT NULL,
  `all_folder_id` int(11) DEFAULT NULL,
  `starred_folder_id` int(11) DEFAULT NULL,
  `important_folder_id` int(11) DEFAULT NULL,
  `sync_host` varchar(255) DEFAULT NULL,
  `state` enum('live','down','invalid') DEFAULT NULL,
  `sync_state` enum('running','stopped','killed','invalid','connerror') DEFAULT NULL,
  `_sync_status` text,
  `type` varchar(16) DEFAULT NULL,
  `last_synced_events` datetime DEFAULT NULL,
  `default_calendar_id` int(11) DEFAULT NULL,
  `throttled` tinyint(1) DEFAULT '0',
  `name` varchar(256) NOT NULL DEFAULT '',
  `sync_events` tinyint(1) NOT NULL,
  `sync_contacts` tinyint(1) NOT NULL,
  `sync_should_run` tinyint(1) DEFAULT '1',
  PRIMARY KEY (`id`),
  KEY `inbox_folder_id` (`inbox_folder_id`),
  KEY `sent_folder_id` (`sent_folder_id`),
  KEY `drafts_folder_id` (`drafts_folder_id`),
  KEY `spam_folder_id` (`spam_folder_id`),
  KEY `trash_folder_id` (`trash_folder_id`),
  KEY `archive_folder_id` (`archive_folder_id`),
  KEY `all_folder_id` (`all_folder_id`),
  KEY `starred_folder_id` (`starred_folder_id`),
  KEY `important_folder_id` (`important_folder_id`),
  KEY `ix_account__raw_address` (`_raw_address`),
  KEY `ix_account_deleted_at` (`deleted_at`),
  KEY `ix_account_created_at` (`created_at`),
  KEY `ix_account__canonicalized_address` (`_canonicalized_address`),
  KEY `ix_account_public_id` (`public_id`),
  KEY `ix_account_updated_at` (`updated_at`),
  KEY `account_ibfk_10` (`default_calendar_id`),
  CONSTRAINT `account_ibfk_10` FOREIGN KEY (`default_calendar_id`) REFERENCES `calendar` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_1` FOREIGN KEY (`inbox_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_2` FOREIGN KEY (`sent_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_3` FOREIGN KEY (`drafts_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_4` FOREIGN KEY (`spam_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_5` FOREIGN KEY (`trash_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_6` FOREIGN KEY (`archive_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_7` FOREIGN KEY (`all_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_8` FOREIGN KEY (`starred_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_9` FOREIGN KEY (`important_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=1297 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `actionlog`
--

DROP TABLE IF EXISTS `actionlog`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `actionlog` (
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `namespace_id` int(11) NOT NULL,
  `action` tinytext NOT NULL,
  `record_id` int(11) NOT NULL,
  `table_name` tinytext NOT NULL,
  `extra_args` text,
  `retries` int(11) NOT NULL DEFAULT '0',
  `status` enum('pending','successful','failed') DEFAULT 'pending',
  PRIMARY KEY (`id`),
  KEY `ix_actionlog_created_at` (`created_at`),
  KEY `ix_actionlog_deleted_at` (`deleted_at`),
  KEY `ix_actionlog_namespace_id` (`namespace_id`),
  KEY `ix_actionlog_updated_at` (`updated_at`),
  KEY `ix_actionlog_status_retries_id` (`status`,`retries`,`id`),
  CONSTRAINT `actionlog_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=927162 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `alembic_version`
--

DROP TABLE IF EXISTS `alembic_version`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `block`
--

DROP TABLE IF EXISTS `block`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `block` (
  `public_id` binary(16) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `size` int(11) DEFAULT NULL,
  `data_sha256` varchar(64) DEFAULT NULL,
  `_content_type_common` enum('text/plain','text/html','multipart/alternative','multipart/mixed','image/jpeg','multipart/related','application/pdf','image/png','image/gif','application/octet-stream','multipart/signed','application/msword','application/pkcs7-signature','message/rfc822','image/jpg') DEFAULT NULL,
  `_content_type_other` varchar(255) DEFAULT NULL,
  `filename` varchar(255) DEFAULT NULL,
  `namespace_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `namespace_id` (`namespace_id`),
  KEY `ix_block_public_id` (`public_id`),
  KEY `ix_block_created_at` (`created_at`),
  KEY `ix_block_deleted_at` (`deleted_at`),
  KEY `ix_block_updated_at` (`updated_at`),
  CONSTRAINT `block_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=131634959 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `calendar`
--

DROP TABLE IF EXISTS `calendar`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `calendar` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `public_id` binary(16) NOT NULL,
  `name` varchar(128) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime DEFAULT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `description` text,
  `uid` varchar(767) CHARACTER SET ascii NOT NULL,
  `read_only` tinyint(1) NOT NULL,
  `provider_name` varchar(128) DEFAULT NULL,
  `namespace_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`namespace_id`,`provider_name`,`name`),
  CONSTRAINT `calendar_ibfk_2` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2076 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `contact`
--

DROP TABLE IF EXISTS `contact`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `contact` (
  `public_id` binary(16) NOT NULL,
  `_raw_address` varchar(191) DEFAULT NULL,
  `_canonicalized_address` varchar(191) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `uid` varchar(64) NOT NULL,
  `provider_name` varchar(64) DEFAULT NULL,
  `source` enum('local','remote') DEFAULT NULL,
  `name` text,
  `raw_data` text,
  `score` int(11) DEFAULT NULL,
  `namespace_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uid` (`uid`,`source`,`namespace_id`,`provider_name`),
  KEY `ix_contact_updated_at` (`updated_at`),
  KEY `ix_contact_deleted_at` (`deleted_at`),
  KEY `ix_contact_created_at` (`created_at`),
  KEY `ix_contact__raw_address` (`_raw_address`),
  KEY `ix_contact__canonicalized_address` (`_canonicalized_address`),
  KEY `ix_contact_public_id` (`public_id`),
  KEY `namespace_id` (`namespace_id`),
  CONSTRAINT `contact_ibfk_2` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4588616 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `easaccount`
--

DROP TABLE IF EXISTS `easaccount`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `easaccount` (
  `id` int(11) NOT NULL,
  `eas_server` varchar(512) DEFAULT NULL,
  `password_id` int(11) NOT NULL,
  `username` varchar(255) DEFAULT NULL,
  `eas_auth` varchar(191) NOT NULL,
  `primary_device_id` int(11) NOT NULL,
  `secondary_device_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `password_id` (`password_id`),
  KEY `primary_device_id` (`primary_device_id`),
  KEY `secondary_device_id` (`secondary_device_id`),
  CONSTRAINT `easaccount_ibfk_1` FOREIGN KEY (`id`) REFERENCES `account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `easaccount_ibfk_2` FOREIGN KEY (`password_id`) REFERENCES `secret` (`id`),
  CONSTRAINT `easaccount_ibfk_3` FOREIGN KEY (`primary_device_id`) REFERENCES `easdevice` (`id`),
  CONSTRAINT `easaccount_ibfk_4` FOREIGN KEY (`secondary_device_id`) REFERENCES `easdevice` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `easdevice`
--

DROP TABLE IF EXISTS `easdevice`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `easdevice` (
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `filtered` tinyint(1) NOT NULL,
  `eas_device_id` varchar(32) NOT NULL,
  `eas_device_type` varchar(32) NOT NULL,
  `eas_policy_key` varchar(64) DEFAULT NULL,
  `eas_sync_key` varchar(64) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `ix_easdevice_created_at` (`created_at`),
  KEY `ix_easdevice_updated_at` (`updated_at`),
  KEY `ix_easdevice_deleted_at` (`deleted_at`),
  KEY `ix_easdevice_eas_device_id` (`eas_device_id`)
) ENGINE=InnoDB AUTO_INCREMENT=251 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `easfoldersyncstatus`
--

DROP TABLE IF EXISTS `easfoldersyncstatus`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `easfoldersyncstatus` (
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `account_id` int(11) NOT NULL,
  `folder_id` int(11) NOT NULL,
  `state` enum('initial','initial keyinvalid','poll','poll keyinvalid','finish') NOT NULL DEFAULT 'initial',
  `eas_folder_sync_key` varchar(64) NOT NULL,
  `eas_folder_id` varchar(64) DEFAULT NULL,
  `eas_folder_type` varchar(64) DEFAULT NULL,
  `eas_parent_id` varchar(64) DEFAULT NULL,
  `_metrics` text,
  `device_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `account_id` (`account_id`,`device_id`,`folder_id`),
  UNIQUE KEY `account_id_2` (`account_id`,`device_id`,`eas_folder_id`),
  KEY `ix_easfoldersyncstatus_deleted_at` (`deleted_at`),
  KEY `ix_easfoldersyncstatus_created_at` (`created_at`),
  KEY `ix_easfoldersyncstatus_updated_at` (`updated_at`),
  KEY `device_id` (`device_id`),
  KEY `easfoldersyncstatus_ibfk_3` (`folder_id`),
  CONSTRAINT `easfoldersyncstatus_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `easaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `easfoldersyncstatus_ibfk_3` FOREIGN KEY (`folder_id`) REFERENCES `folder` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=43530 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `easthread`
--

DROP TABLE IF EXISTS `easthread`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `easthread` (
  `id` int(11) NOT NULL,
  `eas_thrid` blob,
  PRIMARY KEY (`id`),
  KEY `ix_easthread_eas_thrid` (`eas_thrid`(256)),
  CONSTRAINT `easthread_ibfk_1` FOREIGN KEY (`id`) REFERENCES `thread` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `easuid`
--

DROP TABLE IF EXISTS `easuid`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `easuid` (
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `easaccount_id` int(11) NOT NULL,
  `message_id` int(11) NOT NULL,
  `fld_uid` int(11) NOT NULL,
  `msg_uid` int(11) NOT NULL,
  `folder_id` int(11) NOT NULL,
  `is_draft` tinyint(1) NOT NULL,
  `is_flagged` tinyint(1) NOT NULL,
  `is_seen` tinyint(1) DEFAULT NULL,
  `device_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `folder_id` (`folder_id`,`msg_uid`,`easaccount_id`,`device_id`),
  KEY `easuid_easaccount_id_folder_id` (`easaccount_id`,`folder_id`),
  KEY `ix_easuid_created_at` (`created_at`),
  KEY `ix_easuid_msg_uid` (`msg_uid`),
  KEY `ix_easuid_deleted_at` (`deleted_at`),
  KEY `ix_easuid_updated_at` (`updated_at`),
  KEY `device_id` (`device_id`),
  KEY `easuid_ibfk_2` (`message_id`),
  CONSTRAINT `easuid_ibfk_1` FOREIGN KEY (`easaccount_id`) REFERENCES `easaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `easuid_ibfk_2` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`) ON DELETE CASCADE,
  CONSTRAINT `easuid_ibfk_3` FOREIGN KEY (`folder_id`) REFERENCES `folder` (`id`) ON DELETE CASCADE,
  CONSTRAINT `easuid_ibfk_4` FOREIGN KEY (`device_id`) REFERENCES `easdevice` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3211554 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `event`
--

DROP TABLE IF EXISTS `event`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `event` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `uid` varchar(767) CHARACTER SET ascii DEFAULT NULL,
  `provider_name` varchar(64) NOT NULL,
  `public_id` binary(16) NOT NULL,
  `raw_data` text NOT NULL,
  `title` varchar(1024) DEFAULT NULL,
  `description` text,
  `location` varchar(255) DEFAULT NULL,
  `busy` tinyint(1) NOT NULL,
  `reminders` varchar(255) DEFAULT NULL,
  `recurrence` varchar(255) DEFAULT NULL,
  `start` datetime NOT NULL,
  `end` datetime DEFAULT NULL,
  `all_day` tinyint(1) NOT NULL,
  `source` enum('remote','local') NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `calendar_id` int(11) NOT NULL,
  `owner` varchar(255) DEFAULT NULL,
  `is_owner` tinyint(1) NOT NULL,
  `read_only` tinyint(1) NOT NULL,
  `namespace_id` int(11) NOT NULL,
  `participants_by_email` text,
  `participants` longtext,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uid`,`source`,`namespace_id`,`provider_name`),
  KEY `event_ibfk_2` (`calendar_id`),
  KEY `namespace_id` (`namespace_id`),
  CONSTRAINT `event_ibfk_3` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE,
  CONSTRAINT `event_ibfk_2` FOREIGN KEY (`calendar_id`) REFERENCES `calendar` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=87314591 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `folder`
--

DROP TABLE IF EXISTS `folder`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `folder` (
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `account_id` int(11) NOT NULL,
  `name` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `canonical_name` varchar(191) DEFAULT NULL,
  `identifier` varchar(191) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `account_id` (`account_id`,`name`,`canonical_name`,`identifier`),
  KEY `ix_folder_updated_at` (`updated_at`),
  KEY `ix_folder_created_at` (`created_at`),
  KEY `ix_folder_deleted_at` (`deleted_at`),
  CONSTRAINT `folder_fk1` FOREIGN KEY (`account_id`) REFERENCES `account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1046280 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `folderitem`
--

DROP TABLE IF EXISTS `folderitem`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `folderitem` (
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `thread_id` int(11) NOT NULL,
  `folder_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `thread_id` (`thread_id`),
  KEY `folder_id` (`folder_id`),
  KEY `ix_folderitem_created_at` (`created_at`),
  KEY `ix_folderitem_deleted_at` (`deleted_at`),
  KEY `ix_folderitem_updated_at` (`updated_at`),
  CONSTRAINT `folderitem_ibfk_1` FOREIGN KEY (`thread_id`) REFERENCES `thread` (`id`) ON DELETE CASCADE,
  CONSTRAINT `folderitem_ibfk_2` FOREIGN KEY (`folder_id`) REFERENCES `folder` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=41799933 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `genericaccount`
--

DROP TABLE IF EXISTS `genericaccount`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `genericaccount` (
  `id` int(11) NOT NULL,
  `password_id` int(11) NOT NULL,
  `provider` varchar(64) NOT NULL,
  `supports_condstore` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `genericaccount_ibfk_2` (`password_id`),
  CONSTRAINT `genericaccount_ibfk_1` FOREIGN KEY (`id`) REFERENCES `imapaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `genericaccount_ibfk_2` FOREIGN KEY (`password_id`) REFERENCES `secret` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `gmailaccount`
--

DROP TABLE IF EXISTS `gmailaccount`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `gmailaccount` (
  `id` int(11) NOT NULL,
  `refresh_token_id` int(11) NOT NULL,
  `client_id` varchar(256) DEFAULT NULL,
  `client_secret` varchar(256) DEFAULT NULL,
  `scope` varchar(512) DEFAULT NULL,
  `access_type` varchar(64) DEFAULT NULL,
  `family_name` varchar(256) DEFAULT NULL,
  `given_name` varchar(256) DEFAULT NULL,
  `gender` varchar(16) DEFAULT NULL,
  `g_id` varchar(32) DEFAULT NULL,
  `g_id_token` varchar(1024) DEFAULT NULL,
  `g_user_id` varchar(32) DEFAULT NULL,
  `link` varchar(256) DEFAULT NULL,
  `locale` varchar(8) DEFAULT NULL,
  `picture` varchar(1024) DEFAULT NULL,
  `home_domain` varchar(256) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `gmailaccount_ibfk_2` (`refresh_token_id`),
  CONSTRAINT `gmailaccount_ibfk_1` FOREIGN KEY (`id`) REFERENCES `imapaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `gmailaccount_ibfk_2` FOREIGN KEY (`refresh_token_id`) REFERENCES `secret` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `imapaccount`
--

DROP TABLE IF EXISTS `imapaccount`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `imapaccount` (
  `id` int(11) NOT NULL,
  `_imap_server_host` varchar(255) DEFAULT NULL,
  `_imap_server_port` int(11) NOT NULL DEFAULT '993',
  `_smtp_server_host` varchar(255) DEFAULT NULL,
  `_smtp_server_port` int(11) NOT NULL DEFAULT '587',
  PRIMARY KEY (`id`),
  CONSTRAINT `imapaccount_ibfk_1` FOREIGN KEY (`id`) REFERENCES `account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `imapfolderinfo`
--

DROP TABLE IF EXISTS `imapfolderinfo`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `imapfolderinfo` (
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `account_id` int(11) NOT NULL,
  `folder_id` int(11) NOT NULL,
  `uidvalidity` bigint(20) NOT NULL,
  `highestmodseq` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `account_id` (`account_id`,`folder_id`),
  KEY `ix_imapfolderinfo_created_at` (`created_at`),
  KEY `ix_imapfolderinfo_deleted_at` (`deleted_at`),
  KEY `ix_imapfolderinfo_updated_at` (`updated_at`),
  KEY `folder_id` (`folder_id`),
  CONSTRAINT `imapfolderinfo_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `imapaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `imapfolderinfo_ibfk_3` FOREIGN KEY (`folder_id`) REFERENCES `folder` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4601 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `imapfoldersyncstatus`
--

DROP TABLE IF EXISTS `imapfoldersyncstatus`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `imapfoldersyncstatus` (
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `account_id` int(11) NOT NULL,
  `folder_id` int(11) NOT NULL,
  `state` enum('initial','initial uidinvalid','poll','poll uidinvalid','finish') NOT NULL DEFAULT 'initial',
  `_metrics` text,
  PRIMARY KEY (`id`),
  UNIQUE KEY `account_id` (`account_id`,`folder_id`),
  KEY `ix_imapfoldersyncstatus_created_at` (`created_at`),
  KEY `ix_imapfoldersyncstatus_updated_at` (`updated_at`),
  KEY `ix_imapfoldersyncstatus_deleted_at` (`deleted_at`),
  KEY `folder_id` (`folder_id`),
  CONSTRAINT `imapfoldersyncstatus_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `imapaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `imapfoldersyncstatus_ibfk_3` FOREIGN KEY (`folder_id`) REFERENCES `folder` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=6025 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `imapthread`
--

DROP TABLE IF EXISTS `imapthread`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `imapthread` (
  `id` int(11) NOT NULL,
  `g_thrid` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_imapthread_g_thrid` (`g_thrid`),
  CONSTRAINT `imapthread_ibfk_1` FOREIGN KEY (`id`) REFERENCES `thread` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `imapuid`
--

DROP TABLE IF EXISTS `imapuid`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `imapuid` (
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `account_id` int(11) NOT NULL,
  `message_id` int(11) NOT NULL,
  `msg_uid` bigint(20) NOT NULL,
  `folder_id` int(11) NOT NULL,
  `is_draft` tinyint(1) NOT NULL DEFAULT '0',
  `is_seen` tinyint(1) NOT NULL DEFAULT '0',
  `is_flagged` tinyint(1) NOT NULL DEFAULT '0',
  `is_recent` tinyint(1) NOT NULL DEFAULT '0',
  `is_answered` tinyint(1) NOT NULL DEFAULT '0',
  `extra_flags` varchar(255) NOT NULL,
  `g_labels` text,
  PRIMARY KEY (`id`),
  UNIQUE KEY `folder_id` (`folder_id`,`msg_uid`,`account_id`),
  KEY `message_id` (`message_id`),
  KEY `ix_imapuid_deleted_at` (`deleted_at`),
  KEY `ix_imapuid_msg_uid` (`msg_uid`),
  KEY `account_id_folder_id` (`account_id`,`folder_id`),
  KEY `ix_imapuid_created_at` (`created_at`),
  KEY `ix_imapuid_updated_at` (`updated_at`),
  CONSTRAINT `imapuid_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `imapaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `imapuid_ibfk_2` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`) ON DELETE CASCADE,
  CONSTRAINT `imapuid_ibfk_3` FOREIGN KEY (`folder_id`) REFERENCES `folder` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=38132153 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `message`
--

DROP TABLE IF EXISTS `message`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `message` (
  `public_id` binary(16) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `thread_id` int(11) NOT NULL,
  `from_addr` text NOT NULL,
  `sender_addr` text,
  `reply_to` text,
  `to_addr` text NOT NULL,
  `cc_addr` text NOT NULL,
  `bcc_addr` text NOT NULL,
  `in_reply_to` text,
  `message_id_header` varchar(998) DEFAULT NULL,
  `subject` varchar(255) DEFAULT NULL,
  `received_date` datetime NOT NULL,
  `size` int(11) NOT NULL,
  `data_sha256` varchar(255) DEFAULT NULL,
  `is_draft` tinyint(1) NOT NULL DEFAULT '0',
  `is_read` tinyint(1) NOT NULL DEFAULT '0',
  `sanitized_body` longtext NOT NULL,
  `snippet` varchar(191) NOT NULL,
  `decode_error` tinyint(1) NOT NULL DEFAULT '0',
  `g_msgid` bigint(20) DEFAULT NULL,
  `g_thrid` bigint(20) DEFAULT NULL,
  `inbox_uid` varchar(64) DEFAULT NULL,
  `references` text,
  `type` varchar(16) DEFAULT NULL,
  `is_created` tinyint(1) NOT NULL DEFAULT '0',
  `is_sent` tinyint(1) NOT NULL DEFAULT '0',
  `state` enum('draft','sending','sending failed','sent') DEFAULT NULL,
  `is_reply` tinyint(1) DEFAULT NULL,
  `resolved_message_id` int(11) DEFAULT NULL,
  `thread_order` int(11) NOT NULL,
  `version` binary(16) DEFAULT NULL,
  `namespace_id` int(11) NOT NULL,
  `full_body_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `thread_id` (`thread_id`),
  KEY `ix_message_public_id` (`public_id`),
  KEY `ix_message_updated_at` (`updated_at`),
  KEY `ix_message_g_thrid` (`g_thrid`),
  KEY `ix_message_created_at` (`created_at`),
  KEY `ix_message_g_msgid` (`g_msgid`),
  KEY `ix_message_deleted_at` (`deleted_at`),
  KEY `message_ibfk_2` (`resolved_message_id`),
  KEY `ix_message_inbox_uid` (`inbox_uid`),
  KEY `ix_message_received_date` (`received_date`),
  KEY `ix_message_subject` (`subject`(191)),
  KEY `full_body_id_fk` (`full_body_id`),
  KEY `ix_message_ns_id_is_draft_received_date` (`namespace_id`,`is_draft`,`received_date`),
  KEY `ix_message_data_sha256` (`data_sha256`(191)),
  KEY `ix_message_namespace_id_deleted_at` (`namespace_id`,`deleted_at`),
  CONSTRAINT `full_body_id_fk` FOREIGN KEY (`full_body_id`) REFERENCES `block` (`id`),
  CONSTRAINT `message_ibfk_1` FOREIGN KEY (`thread_id`) REFERENCES `thread` (`id`) ON DELETE CASCADE,
  CONSTRAINT `message_ibfk_2` FOREIGN KEY (`resolved_message_id`) REFERENCES `message` (`id`),
  CONSTRAINT `message_ibfk_3` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=34221236 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `messagecontactassociation`
--

DROP TABLE IF EXISTS `messagecontactassociation`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `messagecontactassociation` (
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `contact_id` int(11) NOT NULL,
  `message_id` int(11) NOT NULL,
  `field` enum('from_addr','to_addr','cc_addr','bcc_addr') DEFAULT NULL,
  PRIMARY KEY (`id`,`contact_id`,`message_id`),
  KEY `contact_id` (`contact_id`),
  KEY `message_id` (`message_id`),
  KEY `ix_messagecontactassociation_created_at` (`created_at`),
  KEY `ix_messagecontactassociation_updated_at` (`updated_at`),
  KEY `ix_messagecontactassociation_deleted_at` (`deleted_at`),
  CONSTRAINT `messagecontactassociation_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`id`) ON DELETE CASCADE,
  CONSTRAINT `messagecontactassociation_ibfk_2` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=92021145 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `namespace`
--

DROP TABLE IF EXISTS `namespace`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `namespace` (
  `public_id` binary(16) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `account_id` int(11) DEFAULT NULL,
  `type` enum('root','shared_folder') NOT NULL DEFAULT 'root',
  PRIMARY KEY (`id`),
  KEY `account_id` (`account_id`),
  KEY `ix_namespace_updated_at` (`updated_at`),
  KEY `ix_namespace_deleted_at` (`deleted_at`),
  KEY `ix_namespace_public_id` (`public_id`),
  KEY `ix_namespace_created_at` (`created_at`),
  CONSTRAINT `namespace_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1297 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `outlookaccount`
--

DROP TABLE IF EXISTS `outlookaccount`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `outlookaccount` (
  `id` int(11) NOT NULL,
  `refresh_token_id` int(11) NOT NULL,
  `scope` varchar(512) DEFAULT NULL,
  `locale` varchar(8) DEFAULT NULL,
  `client_id` varchar(256) DEFAULT NULL,
  `client_secret` varchar(256) DEFAULT NULL,
  `o_id` varchar(32) DEFAULT NULL,
  `o_id_token` varchar(1024) DEFAULT NULL,
  `link` varchar(256) DEFAULT NULL,
  `gender` varchar(16) DEFAULT NULL,
  `family_name` varchar(256) DEFAULT NULL,
  `given_name` varchar(256) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `outlookaccount_ibfk_2` (`refresh_token_id`),
  CONSTRAINT `outlookaccount_ibfk_1` FOREIGN KEY (`id`) REFERENCES `imapaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `outlookaccount_ibfk_2` FOREIGN KEY (`refresh_token_id`) REFERENCES `secret` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `part`
--

DROP TABLE IF EXISTS `part`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `part` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `message_id` int(11) DEFAULT NULL,
  `walk_index` int(11) DEFAULT NULL,
  `content_disposition` enum('inline','attachment') DEFAULT NULL,
  `content_id` varchar(255) DEFAULT NULL,
  `is_inboxapp_attachment` tinyint(1) DEFAULT '0',
  `block_id` int(11) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `message_id` (`message_id`,`walk_index`),
  KEY `part_ibfk_1` (`block_id`),
  CONSTRAINT `part_ibfk_1` FOREIGN KEY (`block_id`) REFERENCES `block` (`id`) ON DELETE CASCADE,
  CONSTRAINT `part_ibfk_2` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=101523378 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `searchindexcursor`
--

DROP TABLE IF EXISTS `searchindexcursor`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `searchindexcursor` (
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `transaction_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_searchindexcursor_created_at` (`created_at`),
  KEY `ix_searchindexcursor_deleted_at` (`deleted_at`),
  KEY `ix_searchindexcursor_updated_at` (`updated_at`),
  KEY `ix_searchindexcursor_transaction_id` (`transaction_id`),
  CONSTRAINT `searchindexcursor_ibfk_1` FOREIGN KEY (`transaction_id`) REFERENCES `transaction` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `secret`
--

DROP TABLE IF EXISTS `secret`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `secret` (
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `type` enum('password','token') NOT NULL,
  `encryption_scheme` int(11) NOT NULL DEFAULT '0',
  `_secret` blob NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_secret_updated_at` (`updated_at`),
  KEY `ix_secret_created_at` (`created_at`),
  KEY `ix_secret_deleted_at` (`deleted_at`)
) ENGINE=InnoDB AUTO_INCREMENT=1652 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tag`
--

DROP TABLE IF EXISTS `tag`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tag` (
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `namespace_id` int(11) NOT NULL,
  `public_id` varchar(191) NOT NULL,
  `name` varchar(191) NOT NULL,
  `user_created` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `namespace_id` (`namespace_id`,`name`),
  UNIQUE KEY `namespace_id_2` (`namespace_id`,`public_id`),
  KEY `ix_tag_updated_at` (`updated_at`),
  KEY `ix_tag_created_at` (`created_at`),
  KEY `ix_tag_deleted_at` (`deleted_at`),
  CONSTRAINT `tag_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=102034 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tagitem`
--

DROP TABLE IF EXISTS `tagitem`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tagitem` (
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `thread_id` int(11) NOT NULL,
  `tag_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `thread_id` (`thread_id`),
  KEY `tag_id` (`tag_id`),
  KEY `ix_tagitem_created_at` (`created_at`),
  KEY `ix_tagitem_deleted_at` (`deleted_at`),
  KEY `ix_tagitem_updated_at` (`updated_at`),
  CONSTRAINT `tagitem_ibfk_2` FOREIGN KEY (`tag_id`) REFERENCES `tag` (`id`) ON DELETE CASCADE,
  CONSTRAINT `tagitem_ibfk_1` FOREIGN KEY (`thread_id`) REFERENCES `thread` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=80146012 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `thread`
--

DROP TABLE IF EXISTS `thread`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `thread` (
  `public_id` binary(16) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `subject` varchar(255) DEFAULT NULL,
  `subjectdate` datetime NOT NULL,
  `recentdate` datetime NOT NULL,
  `snippet` varchar(191) DEFAULT NULL,
  `namespace_id` int(11) NOT NULL,
  `type` varchar(16) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_thread_created_at` (`created_at`),
  KEY `ix_thread_deleted_at` (`deleted_at`),
  KEY `ix_thread_public_id` (`public_id`),
  KEY `ix_thread_namespace_id` (`namespace_id`),
  KEY `ix_thread_updated_at` (`updated_at`),
  KEY `ix_thread_recentdate` (`recentdate`),
  KEY `ix_thread_subjectdate` (`subjectdate`),
  KEY `ix_thread_subject` (`subject`(191)),
  KEY `ix_thread_namespace_id_recentdate_deleted_at` (`namespace_id`,`recentdate`,`deleted_at`),
  CONSTRAINT `thread_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=18251577 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `transaction`
--

DROP TABLE IF EXISTS `transaction`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `transaction` (
  `public_id` binary(16) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `object_type` varchar(20) NOT NULL,
  `record_id` int(11) NOT NULL,
  `command` enum('insert','update','delete') NOT NULL,
  `namespace_id` int(11) NOT NULL,
  `object_public_id` varchar(191) NOT NULL,
  `snapshot` longtext,
  PRIMARY KEY (`id`),
  KEY `ix_transaction_created_at` (`created_at`),
  KEY `ix_transaction_deleted_at` (`deleted_at`),
  KEY `namespace_id_deleted_at` (`namespace_id`,`deleted_at`),
  KEY `ix_transaction_public_id` (`public_id`),
  KEY `ix_transaction_updated_at` (`updated_at`),
  KEY `ix_transaction_record_id` (`record_id`),
  KEY `ix_transaction_table_name` (`object_type`),
  KEY `ix_transaction_object_public_id` (`object_public_id`),
  KEY `namespace_id_created_at` (`namespace_id`,`created_at`),
  CONSTRAINT `transaction_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=456895720 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2015-02-24 18:52:25
