-- MySQL dump 10.13  Distrib 5.5.38, for debian-linux-gnu (x86_64)
--
-- Host: localhost    Database: test
-- ------------------------------------------------------
-- Server version	5.5.38-0ubuntu0.12.04.1-log

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
  `name` varchar(256) NOT NULL DEFAULT '',
  `throttled` tinyint(1) DEFAULT '0',
  `save_raw_messages` tinyint(1) DEFAULT '1',
  `sync_contacts` tinyint(1) NOT NULL,
  `sync_events` tinyint(1) NOT NULL,
  `last_synced_contacts` datetime DEFAULT NULL,
  `last_synced_events` datetime DEFAULT NULL,
  `inbox_folder_id` int(11) DEFAULT NULL,
  `sent_folder_id` int(11) DEFAULT NULL,
  `drafts_folder_id` int(11) DEFAULT NULL,
  `spam_folder_id` int(11) DEFAULT NULL,
  `trash_folder_id` int(11) DEFAULT NULL,
  `archive_folder_id` int(11) DEFAULT NULL,
  `all_folder_id` int(11) DEFAULT NULL,
  `starred_folder_id` int(11) DEFAULT NULL,
  `important_folder_id` int(11) DEFAULT NULL,
  `emailed_events_calendar_id` int(11) DEFAULT NULL,
  `sync_host` varchar(255) DEFAULT NULL,
  `state` enum('live','down','invalid') DEFAULT NULL,
  `sync_state` enum('running','stopped','killed','invalid','connerror') DEFAULT NULL,
  `sync_should_run` tinyint(1) DEFAULT '1',
  `_sync_status` text,
  `type` varchar(16) DEFAULT NULL,
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
  KEY `ix_account_public_id` (`public_id`),
  KEY `ix_account__canonicalized_address` (`_canonicalized_address`),
  KEY `ix_account_updated_at` (`updated_at`),
  KEY `ix_account_created_at` (`created_at`),
  KEY `emailed_events_cal` (`emailed_events_calendar_id`),
  CONSTRAINT `emailed_events_cal` FOREIGN KEY (`emailed_events_calendar_id`) REFERENCES `calendar` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_1` FOREIGN KEY (`inbox_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_2` FOREIGN KEY (`sent_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_3` FOREIGN KEY (`drafts_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_4` FOREIGN KEY (`spam_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_5` FOREIGN KEY (`trash_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_6` FOREIGN KEY (`archive_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_7` FOREIGN KEY (`all_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_8` FOREIGN KEY (`starred_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL,
  CONSTRAINT `account_ibfk_9` FOREIGN KEY (`important_folder_id`) REFERENCES `folder` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `account`
--

LOCK TABLES `account` WRITE;
/*!40000 ALTER TABLE `account` DISABLE KEYS */;
INSERT INTO `account` VALUES ('ÅÇÅwC6ç√sfm','inboxapptest@gmail.com','inboxapptest@gmail.com','2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,1,'Inbox App',0,1,1,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,1,NULL,NULL,NULL,1,'{}','gmailaccount'),('Ñ≠âeHfï@w>&','test@nilas.com','test@nilas.com','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,2,'',0,1,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,2,NULL,NULL,NULL,1,'{}','account');
/*!40000 ALTER TABLE `account` ENABLE KEYS */;
UNLOCK TABLES;

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
  `status` enum('pending','successful','failed') DEFAULT 'pending',
  `retries` int(11) NOT NULL DEFAULT '0',
  `extra_args` text,
  `type` varchar(16) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_actionlog_created_at` (`created_at`),
  KEY `ix_actionlog_status_retries` (`status`,`retries`),
  KEY `ix_actionlog_deleted_at` (`deleted_at`),
  KEY `ix_actionlog_namespace_id` (`namespace_id`),
  KEY `ix_actionlog_updated_at` (`updated_at`),
  CONSTRAINT `actionlog_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `actionlog`
--

LOCK TABLES `actionlog` WRITE;
/*!40000 ALTER TABLE `actionlog` DISABLE KEYS */;
/*!40000 ALTER TABLE `actionlog` ENABLE KEYS */;
UNLOCK TABLES;

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
-- Dumping data for table `alembic_version`
--

LOCK TABLES `alembic_version` WRITE;
/*!40000 ALTER TABLE `alembic_version` DISABLE KEYS */;
INSERT INTO `alembic_version` VALUES ('365071c47fa7');
/*!40000 ALTER TABLE `alembic_version` ENABLE KEYS */;
UNLOCK TABLES;

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
  KEY `ix_block_deleted_at` (`deleted_at`),
  KEY `ix_block_public_id` (`public_id`),
  KEY `ix_block_created_at` (`created_at`),
  KEY `ix_block_updated_at` (`updated_at`),
  CONSTRAINT `block_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `block`
--

LOCK TABLES `block` WRITE;
/*!40000 ALTER TABLE `block` DISABLE KEYS */;
INSERT INTO `block` VALUES (':uPöSI§-.√Ã˝','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,1,16089,'b2baa4d84975bc4a340496bca4327b74fd36f66cb8c9d03985e99fed9e185125','text/plain',NULL,NULL,1),('Ë|6Æ”AêìjØi”fy`','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,2,7532,'0b0148018680d39e5d55c9ce717eb21900da9bcfc56cd31d8e7679ecedbbba32',NULL,NULL,NULL,1),('‰I$I(›A˛ëT-iì}','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,3,2970,'24d36cd57a8837828e64c6301bf39bbe0464ff644a9b960c5f0fedfdb9dec084','text/plain',NULL,NULL,1),('æ\\‚µ«≥Géòﬂ—GéHÓ','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,4,5029,'5eb1c5bd82d20f84df4f79f909fff4b9d52f18e602bb2682e259683949d620b1','text/html',NULL,NULL,1),('3iÜDF∫@,Æı?˛,∫†¿','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,5,134,'1813d67dd6945f6024734ff8b9885ba68453fe2281b4d39a6bae4f5f5d3c85c6','text/plain',NULL,'Attached Message Part',1),('è’~ÿw¡G&åßÎ ˝|Ù','2015-05-08 02:33:29','2015-05-08 02:33:29',NULL,6,16089,'b2baa4d84975bc4a340496bca4327b74fd36f66cb8c9d03985e99fed9e185125','text/plain',NULL,NULL,2),('Dyj_“AåçŸ\Z_	zI','2015-05-08 02:33:29','2015-05-08 02:33:29',NULL,7,7532,'0b0148018680d39e5d55c9ce717eb21900da9bcfc56cd31d8e7679ecedbbba32',NULL,NULL,NULL,2),('≥ﬂ˙\\XèJl∏—)/°Hn','2015-05-08 02:33:29','2015-05-08 02:33:29',NULL,8,2970,'24d36cd57a8837828e64c6301bf39bbe0464ff644a9b960c5f0fedfdb9dec084','text/plain',NULL,NULL,2),('®{l∆5H µQ≈ ˚√-&','2015-05-08 02:33:29','2015-05-08 02:33:29',NULL,9,5029,'5eb1c5bd82d20f84df4f79f909fff4b9d52f18e602bb2682e259683949d620b1','text/html',NULL,NULL,2),('ØªΩXØGóª|*∑Ï¿[','2015-05-08 02:33:29','2015-05-08 02:33:29',NULL,10,134,'1813d67dd6945f6024734ff8b9885ba68453fe2281b4d39a6bae4f5f5d3c85c6','text/plain',NULL,'Attached Message Part',2);
/*!40000 ALTER TABLE `block` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `calendar`
--

DROP TABLE IF EXISTS `calendar`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `calendar` (
  `public_id` binary(16) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `namespace_id` int(11) NOT NULL,
  `name` varchar(128) DEFAULT NULL,
  `provider_name` varchar(128) DEFAULT NULL,
  `description` text,
  `uid` varchar(767) CHARACTER SET ascii NOT NULL,
  `read_only` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`namespace_id`,`provider_name`,`name`,`uid`),
  KEY `ix_calendar_created_at` (`created_at`),
  KEY `ix_calendar_deleted_at` (`deleted_at`),
  KEY `ix_calendar_public_id` (`public_id`),
  KEY `ix_calendar_updated_at` (`updated_at`),
  CONSTRAINT `calendar_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `calendar`
--

LOCK TABLES `calendar` WRITE;
/*!40000 ALTER TABLE `calendar` DISABLE KEYS */;
INSERT INTO `calendar` VALUES ('Ø∂’≈CO‰∑ŸjD◊≈wN','2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,1,1,'Emailed events','DEPRECATED','Emailed events','inbox',1),('/?î≠]GıûﬁOÀI,ü','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,2,2,'Emailed events','DEPRECATED','Emailed events','inbox',1);
/*!40000 ALTER TABLE `calendar` ENABLE KEYS */;
UNLOCK TABLES;

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
  `namespace_id` int(11) NOT NULL,
  `uid` varchar(64) NOT NULL,
  `provider_name` varchar(64) DEFAULT NULL,
  `name` text,
  `raw_data` text,
  `score` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uid` (`uid`,`namespace_id`,`provider_name`),
  KEY `ix_contact_created_at` (`created_at`),
  KEY `ix_contact_updated_at` (`updated_at`),
  KEY `ix_contact_public_id` (`public_id`),
  KEY `ix_contact__canonicalized_address` (`_canonicalized_address`),
  KEY `ix_contact__raw_address` (`_raw_address`),
  KEY `ix_contact_ns_uid_provider_name` (`namespace_id`,`uid`,`provider_name`),
  KEY `ix_contact_deleted_at` (`deleted_at`),
  CONSTRAINT `contact_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `contact`
--

LOCK TABLES `contact` WRITE;
/*!40000 ALTER TABLE `contact` DISABLE KEYS */;
/*!40000 ALTER TABLE `contact` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `easaccount`
--

DROP TABLE IF EXISTS `easaccount`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `easaccount` (
  `id` int(11) NOT NULL,
  `username` varchar(255) DEFAULT NULL,
  `password_id` int(11) NOT NULL,
  `eas_auth` varchar(191) NOT NULL,
  `eas_server` varchar(512) DEFAULT NULL,
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
-- Dumping data for table `easaccount`
--

LOCK TABLES `easaccount` WRITE;
/*!40000 ALTER TABLE `easaccount` DISABLE KEYS */;
/*!40000 ALTER TABLE `easaccount` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `easactionlog`
--

DROP TABLE IF EXISTS `easactionlog`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `easactionlog` (
  `id` int(11) NOT NULL,
  `secondary_status` enum('pending','successful','failed') DEFAULT 'pending',
  `secondary_retries` int(11) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  CONSTRAINT `easactionlog_ibfk_1` FOREIGN KEY (`id`) REFERENCES `actionlog` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `easactionlog`
--

LOCK TABLES `easactionlog` WRITE;
/*!40000 ALTER TABLE `easactionlog` DISABLE KEYS */;
/*!40000 ALTER TABLE `easactionlog` ENABLE KEYS */;
UNLOCK TABLES;

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
  `inbox_foldersync_id` int(11) DEFAULT NULL,
  `sent_foldersync_id` int(11) DEFAULT NULL,
  `trash_foldersync_id` int(11) DEFAULT NULL,
  `archive_foldersync_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_easdevice_eas_device_id` (`eas_device_id`),
  KEY `ix_easdevice_updated_at` (`updated_at`),
  KEY `ix_easdevice_created_at` (`created_at`),
  KEY `ix_easdevice_deleted_at` (`deleted_at`),
  KEY `inbox_foldersync_ibfk` (`inbox_foldersync_id`),
  KEY `sent_foldersync_ibfk` (`sent_foldersync_id`),
  KEY `trash_foldersync_ibfk` (`trash_foldersync_id`),
  KEY `archive_foldersync_ibfk` (`archive_foldersync_id`),
  CONSTRAINT `archive_foldersync_ibfk` FOREIGN KEY (`archive_foldersync_id`) REFERENCES `easfoldersyncstatus` (`id`) ON DELETE SET NULL,
  CONSTRAINT `inbox_foldersync_ibfk` FOREIGN KEY (`inbox_foldersync_id`) REFERENCES `easfoldersyncstatus` (`id`) ON DELETE SET NULL,
  CONSTRAINT `sent_foldersync_ibfk` FOREIGN KEY (`sent_foldersync_id`) REFERENCES `easfoldersyncstatus` (`id`) ON DELETE SET NULL,
  CONSTRAINT `trash_foldersync_ibfk` FOREIGN KEY (`trash_foldersync_id`) REFERENCES `easfoldersyncstatus` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `easdevice`
--

LOCK TABLES `easdevice` WRITE;
/*!40000 ALTER TABLE `easdevice` DISABLE KEYS */;
/*!40000 ALTER TABLE `easdevice` ENABLE KEYS */;
UNLOCK TABLES;

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
  `device_id` int(11) NOT NULL,
  `name` varchar(191) NOT NULL,
  `canonical_name` varchar(191) DEFAULT NULL,
  `state` enum('initial','initial keyinvalid','poll','poll keyinvalid','finish') NOT NULL DEFAULT 'initial',
  `eas_folder_sync_key` varchar(64) NOT NULL,
  `eas_folder_id` varchar(64) DEFAULT NULL,
  `eas_folder_type` varchar(64) DEFAULT NULL,
  `eas_parent_id` varchar(64) DEFAULT NULL,
  `_metrics` text,
  PRIMARY KEY (`id`),
  UNIQUE KEY `account_id` (`account_id`,`device_id`,`eas_folder_id`),
  KEY `device_id` (`device_id`),
  KEY `ix_easfoldersyncstatus_created_at` (`created_at`),
  KEY `ix_easfoldersyncstatus_updated_at` (`updated_at`),
  KEY `ix_easfoldersyncstatus_deleted_at` (`deleted_at`),
  CONSTRAINT `easfoldersyncstatus_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `easaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `easfoldersyncstatus_ibfk_2` FOREIGN KEY (`device_id`) REFERENCES `easdevice` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `easfoldersyncstatus`
--

LOCK TABLES `easfoldersyncstatus` WRITE;
/*!40000 ALTER TABLE `easfoldersyncstatus` DISABLE KEYS */;
/*!40000 ALTER TABLE `easfoldersyncstatus` ENABLE KEYS */;
UNLOCK TABLES;

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
-- Dumping data for table `easthread`
--

LOCK TABLES `easthread` WRITE;
/*!40000 ALTER TABLE `easthread` DISABLE KEYS */;
/*!40000 ALTER TABLE `easthread` ENABLE KEYS */;
UNLOCK TABLES;

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
  `device_id` int(11) NOT NULL,
  `message_id` int(11) NOT NULL,
  `fld_uid` int(11) NOT NULL,
  `msg_uid` int(11) NOT NULL,
  `is_draft` tinyint(1) NOT NULL DEFAULT '0',
  `is_flagged` tinyint(1) NOT NULL,
  `is_seen` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `easaccount_id` (`easaccount_id`,`device_id`,`fld_uid`,`msg_uid`),
  KEY `device_id` (`device_id`),
  KEY `message_id` (`message_id`),
  KEY `ix_easuid_created_at` (`created_at`),
  KEY `ix_easuid_updated_at` (`updated_at`),
  KEY `ix_easuid_msg_uid` (`msg_uid`),
  KEY `ix_easuid_deleted_at` (`deleted_at`),
  CONSTRAINT `easuid_ibfk_1` FOREIGN KEY (`easaccount_id`) REFERENCES `easaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `easuid_ibfk_2` FOREIGN KEY (`device_id`) REFERENCES `easdevice` (`id`) ON DELETE CASCADE,
  CONSTRAINT `easuid_ibfk_3` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `easuid`
--

LOCK TABLES `easuid` WRITE;
/*!40000 ALTER TABLE `easuid` DISABLE KEYS */;
/*!40000 ALTER TABLE `easuid` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `event`
--

DROP TABLE IF EXISTS `event`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `event` (
  `public_id` binary(16) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `namespace_id` int(11) NOT NULL,
  `calendar_id` int(11) NOT NULL,
  `uid` varchar(767) CHARACTER SET ascii NOT NULL,
  `provider_name` varchar(64) NOT NULL,
  `source` enum('local','remote') DEFAULT NULL,
  `raw_data` text NOT NULL,
  `title` varchar(1024) DEFAULT NULL,
  `owner` varchar(1024) DEFAULT NULL,
  `description` text,
  `location` varchar(255) DEFAULT NULL,
  `busy` tinyint(1) NOT NULL,
  `read_only` tinyint(1) NOT NULL,
  `reminders` varchar(255) DEFAULT NULL,
  `recurrence` text,
  `start` datetime NOT NULL,
  `end` datetime DEFAULT NULL,
  `all_day` tinyint(1) NOT NULL,
  `is_owner` tinyint(1) NOT NULL,
  `last_modified` datetime DEFAULT NULL,
  `status` enum('confirmed','tentative','cancelled') DEFAULT 'confirmed',
  `message_id` int(11) DEFAULT NULL,
  `participants` longtext,
  `type` varchar(30) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `calendar_id` (`calendar_id`),
  KEY `message_id` (`message_id`),
  KEY `ix_event_deleted_at` (`deleted_at`),
  KEY `ix_event_created_at` (`created_at`),
  KEY `ix_event_ns_uid_calendar_id` (`namespace_id`,`uid`,`calendar_id`),
  KEY `ix_event_public_id` (`public_id`),
  KEY `ix_event_updated_at` (`updated_at`),
  CONSTRAINT `event_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE,
  CONSTRAINT `event_ibfk_2` FOREIGN KEY (`calendar_id`) REFERENCES `calendar` (`id`) ON DELETE CASCADE,
  CONSTRAINT `event_ibfk_3` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `event`
--

LOCK TABLES `event` WRITE;
/*!40000 ALTER TABLE `event` DISABLE KEYS */;
/*!40000 ALTER TABLE `event` ENABLE KEYS */;
UNLOCK TABLES;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `folder`
--

LOCK TABLES `folder` WRITE;
/*!40000 ALTER TABLE `folder` DISABLE KEYS */;
/*!40000 ALTER TABLE `folder` ENABLE KEYS */;
UNLOCK TABLES;

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
  KEY `ix_folderitem_updated_at` (`updated_at`),
  KEY `ix_folderitem_deleted_at` (`deleted_at`),
  CONSTRAINT `folderitem_ibfk_1` FOREIGN KEY (`thread_id`) REFERENCES `thread` (`id`) ON DELETE CASCADE,
  CONSTRAINT `folderitem_ibfk_2` FOREIGN KEY (`folder_id`) REFERENCES `folder` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `folderitem`
--

LOCK TABLES `folderitem` WRITE;
/*!40000 ALTER TABLE `folderitem` DISABLE KEYS */;
/*!40000 ALTER TABLE `folderitem` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `genericaccount`
--

DROP TABLE IF EXISTS `genericaccount`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `genericaccount` (
  `id` int(11) NOT NULL,
  `provider` varchar(64) DEFAULT NULL,
  `supports_condstore` tinyint(1) DEFAULT NULL,
  `password_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `password_id` (`password_id`),
  CONSTRAINT `genericaccount_ibfk_1` FOREIGN KEY (`id`) REFERENCES `imapaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `genericaccount_ibfk_2` FOREIGN KEY (`password_id`) REFERENCES `secret` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `genericaccount`
--

LOCK TABLES `genericaccount` WRITE;
/*!40000 ALTER TABLE `genericaccount` DISABLE KEYS */;
/*!40000 ALTER TABLE `genericaccount` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `gmailaccount`
--

DROP TABLE IF EXISTS `gmailaccount`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `gmailaccount` (
  `id` int(11) NOT NULL,
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
  `refresh_token_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `refresh_token_id` (`refresh_token_id`),
  CONSTRAINT `gmailaccount_ibfk_1` FOREIGN KEY (`id`) REFERENCES `imapaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `gmailaccount_ibfk_2` FOREIGN KEY (`refresh_token_id`) REFERENCES `secret` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `gmailaccount`
--

LOCK TABLES `gmailaccount` WRITE;
/*!40000 ALTER TABLE `gmailaccount` DISABLE KEYS */;
INSERT INTO `gmailaccount` VALUES (1,NULL,NULL,'https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile https://mail.google.com/ https://www.google.com/m8/feeds https://www.googleapis.com/auth/calendar',NULL,'App','Inbox','other','115086935419017912828','eyJhbGciOiJSUzI1NiIsImtpZCI6IjgwNmFlMDIxZjNmZDA5M2EzYWIzODE1NjQwMzUzMjhiMDQ0MjNlNmYifQ.eyJpc3MiOiJhY2NvdW50cy5nb29nbGUuY29tIiwic3ViIjoiMTE1MDg2OTM1NDE5MDE3OTEyODI4IiwiYXpwIjoiOTg2NjU5Nzc2NTE2LWZnNzltcWJrYmt0ZjVrdTEwYzIxNXZkaWo5MThyYTBhLmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29tIiwiZW1haWwiOiJpbmJveGFwcHRlc3RAZ21haWwuY29tIiwiYXRfaGFzaCI6IjZxRUE4cGlxM2ZEejdCYjE0T0xjZ3ciLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiYXVkIjoiOTg2NjU5Nzc2NTE2LWZnNzltcWJrYmt0ZjVrdTEwYzIxNXZkaWo5MThyYTBhLmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29tIiwiaWF0IjoxNDMxMDUxMDkwLCJleHAiOjE0MzEwNTQ2OTB9.TqzA5oEDP1iBEmAtWYbUGniUFX3JBDBZMjjdX0bbTWc1EQYGEqzkDcA86Pz9wY3iOANY-ewMpGS7xOjBgApIIP2at_7_BdyI18B11auP_T6qjORkbmMwaiQ1K0BEQD9EUb-G3F11BEqP274LduZGNATk7hlzGoC2ShcvCB_is-c','115086935419017912828',NULL,'en','https://lh3.googleusercontent.com/-XdUIqdMkCWA/AAAAAAAAAAI/AAAAAAAAAAA/4252rscbv5M/photo.jpg',NULL,1);
/*!40000 ALTER TABLE `gmailaccount` ENABLE KEYS */;
UNLOCK TABLES;

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
-- Dumping data for table `imapaccount`
--

LOCK TABLES `imapaccount` WRITE;
/*!40000 ALTER TABLE `imapaccount` DISABLE KEYS */;
INSERT INTO `imapaccount` VALUES (1,NULL,993,NULL,587);
/*!40000 ALTER TABLE `imapaccount` ENABLE KEYS */;
UNLOCK TABLES;

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
  KEY `folder_id` (`folder_id`),
  KEY `ix_imapfolderinfo_deleted_at` (`deleted_at`),
  KEY `ix_imapfolderinfo_created_at` (`created_at`),
  KEY `ix_imapfolderinfo_updated_at` (`updated_at`),
  CONSTRAINT `imapfolderinfo_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `imapaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `imapfolderinfo_ibfk_2` FOREIGN KEY (`folder_id`) REFERENCES `folder` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `imapfolderinfo`
--

LOCK TABLES `imapfolderinfo` WRITE;
/*!40000 ALTER TABLE `imapfolderinfo` DISABLE KEYS */;
/*!40000 ALTER TABLE `imapfolderinfo` ENABLE KEYS */;
UNLOCK TABLES;

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
  KEY `folder_id` (`folder_id`),
  KEY `ix_imapfoldersyncstatus_created_at` (`created_at`),
  KEY `ix_imapfoldersyncstatus_updated_at` (`updated_at`),
  KEY `ix_imapfoldersyncstatus_deleted_at` (`deleted_at`),
  CONSTRAINT `imapfoldersyncstatus_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `imapaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `imapfoldersyncstatus_ibfk_2` FOREIGN KEY (`folder_id`) REFERENCES `folder` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `imapfoldersyncstatus`
--

LOCK TABLES `imapfoldersyncstatus` WRITE;
/*!40000 ALTER TABLE `imapfoldersyncstatus` DISABLE KEYS */;
/*!40000 ALTER TABLE `imapfoldersyncstatus` ENABLE KEYS */;
UNLOCK TABLES;

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
-- Dumping data for table `imapthread`
--

LOCK TABLES `imapthread` WRITE;
/*!40000 ALTER TABLE `imapthread` DISABLE KEYS */;
/*!40000 ALTER TABLE `imapthread` ENABLE KEYS */;
UNLOCK TABLES;

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
  KEY `account_id_folder_id` (`account_id`,`folder_id`),
  KEY `ix_imapuid_created_at` (`created_at`),
  KEY `ix_imapuid_msg_uid` (`msg_uid`),
  KEY `ix_imapuid_updated_at` (`updated_at`),
  CONSTRAINT `imapuid_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `imapaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `imapuid_ibfk_2` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`) ON DELETE CASCADE,
  CONSTRAINT `imapuid_ibfk_3` FOREIGN KEY (`folder_id`) REFERENCES `folder` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `imapuid`
--

LOCK TABLES `imapuid` WRITE;
/*!40000 ALTER TABLE `imapuid` DISABLE KEYS */;
/*!40000 ALTER TABLE `imapuid` ENABLE KEYS */;
UNLOCK TABLES;

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
  `namespace_id` int(11) NOT NULL,
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
  `is_read` tinyint(1) NOT NULL DEFAULT '0',
  `is_draft` tinyint(1) NOT NULL DEFAULT '0',
  `is_sent` tinyint(1) NOT NULL DEFAULT '0',
  `state` enum('draft','sending','sending failed','sent') DEFAULT NULL,
  `sanitized_body` longtext NOT NULL,
  `snippet` varchar(191) NOT NULL,
  `full_body_id` int(11) DEFAULT NULL,
  `decode_error` tinyint(1) NOT NULL DEFAULT '0',
  `g_msgid` bigint(20) DEFAULT NULL,
  `g_thrid` bigint(20) DEFAULT NULL,
  `inbox_uid` varchar(64) DEFAULT NULL,
  `references` text,
  `version` int(11) NOT NULL DEFAULT '0',
  `is_created` tinyint(1) NOT NULL DEFAULT '0',
  `is_reply` tinyint(1) DEFAULT NULL,
  `reply_to_message_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `thread_id` (`thread_id`),
  KEY `full_body_id_fk` (`full_body_id`),
  KEY `reply_to_message_id` (`reply_to_message_id`),
  KEY `ix_message_received_date` (`received_date`),
  KEY `ix_message_updated_at` (`updated_at`),
  KEY `ix_message_g_thrid` (`g_thrid`),
  KEY `ix_message_created_at` (`created_at`),
  KEY `ix_message_deleted_at` (`deleted_at`),
  KEY `ix_message_public_id` (`public_id`),
  KEY `ix_message_namespace_id_deleted_at` (`namespace_id`,`deleted_at`),
  KEY `ix_message_ns_id_is_draft_received_date` (`namespace_id`,`is_draft`,`received_date`),
  KEY `ix_message_g_msgid` (`g_msgid`),
  KEY `ix_message_subject` (`subject`(191)),
  KEY `ix_message_data_sha256` (`data_sha256`(191)),
  KEY `ix_message_namespace_id` (`namespace_id`),
  KEY `ix_message_inbox_uid` (`inbox_uid`),
  CONSTRAINT `message_ibfk_1` FOREIGN KEY (`thread_id`) REFERENCES `thread` (`id`) ON DELETE CASCADE,
  CONSTRAINT `message_ibfk_2` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE,
  CONSTRAINT `full_body_id_fk` FOREIGN KEY (`full_body_id`) REFERENCES `block` (`id`),
  CONSTRAINT `message_ibfk_3` FOREIGN KEY (`reply_to_message_id`) REFERENCES `message` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `message`
--

LOCK TABLES `message` WRITE;
/*!40000 ALTER TABLE `message` DISABLE KEYS */;
INSERT INTO `message` VALUES ('úv%C`Bıò#“≠»èƒ','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,1,1,1,'[[\"Tomaso Poggio\", \"tp@ai.mit.edu\"]]','[[\"\", \"csail-announce-bounces@lists.csail.mit.edu\"]]','[]','[[\"\", \"csail-announce@csail.mit.edu\"], [\"\", \"csail-related@csail.mit.edu\"], [\"\", \"csail-all.lists@mit.edu\"]]','[]','[]','\"<54204C4C.1070008@csail.mit.edu>\"','<54205B6D.10308@ai.mit.edu>','Fwd: Fwd: Talk: Tuesday 09-23-2014 The Integrated Information Theory	of Consciousness','2014-09-22 17:25:46',16089,'b2baa4d84975bc4a340496bca4327b74fd36f66cb8c9d03985e99fed9e185125',0,0,0,NULL,'<html>\n  <head>\n\n    <meta http-equiv=\"content-type\" content=\"text/html; charset=ISO-8859-1\">\n  </head>\n  <body bgcolor=\"#FFFFFF\" text=\"#000000\">\n    <br>\n    <div class=\"moz-forward-container\"><br>\n      <br>\n      -------- Original Message --------\n      <table class=\"moz-email-headers-table\" border=\"0\" cellpadding=\"0\"\n        cellspacing=\"0\">\n        <tbody>\n          <tr>\n            <th align=\"RIGHT\" nowrap=\"nowrap\" valign=\"BASELINE\">Subject:\n            </th>\n            <td>Fwd: Talk: Tuesday 09-23-2014 The Integrated Information\n              Theory of Consciousness</td>\n          </tr>\n          <tr>\n            <th align=\"RIGHT\" nowrap=\"nowrap\" valign=\"BASELINE\">Date: </th>\n            <td>Mon, 22 Sep 2014 12:20:28 -0400</td>\n          </tr>\n          <tr>\n            <th align=\"RIGHT\" nowrap=\"nowrap\" valign=\"BASELINE\">From: </th>\n            <td>Kathleen Sullivan <a class=\"moz-txt-link-rfc2396E\" href=\"mailto:kdsulliv@csail.mit.edu\">&lt;kdsulliv@csail.mit.edu&gt;</a></td>\n          </tr>\n          <tr>\n            <th align=\"RIGHT\" nowrap=\"nowrap\" valign=\"BASELINE\">To: </th>\n            <td><a class=\"moz-txt-link-abbreviated\" href=\"mailto:bcs-all@mit.edu\">bcs-all@mit.edu</a> <a class=\"moz-txt-link-rfc2396E\" href=\"mailto:bcs-all@mit.edu\">&lt;bcs-all@mit.edu&gt;</a></td>\n          </tr>\n        </tbody>\n      </table>\n      <br>\n      <br>\n      <meta http-equiv=\"content-type\" content=\"text/html;\n        charset=ISO-8859-1\">\n      <b>Brains, Minds and Machines Seminar Series </b><br>\n      <div class=\"moz-forward-container\">\n        <h2>The Integrated Information Theory of Consciousness</h2>\n        Speaker: Dr. Christof Koch, Chief Scientific Officer, Allen\n        Institute for Brain Science <br>\n        Date: Tuesday, September 23, 2014 <br>\n        Time: 4:00 PM<br>\n        Location: Singleton Auditorium, MIT 46-3002, 43 Vassar St.,\n        Cambridge MA<br>\n        Host: Prof. Tomaso Poggio, Director CBMM<br>\n        <br>\n        Abstract:&Acirc;&nbsp; The science of consciousness has made great strides\n        by focusing on the behavioral and neuronal correlates of\n        experience. However, such correlates are not enough if we are to\n        understand even basic facts, for example, why the cerebral\n        cortex gives rise to consciousness but the cerebellum does not,\n        though it has even more neurons and appears to be just as\n        complicated. Moreover, correlates are of little help in many\n        instances where we would like to know if consciousness is\n        present: patients with a few remaining islands of functioning\n        cortex, pre-term infants, non-mammalian species, and machines\n        that are rapidly outperforming people at driving, recognizing\n        faces and objects, and answering difficult questions. To address\n        these issues, we need a theory of consciousness &acirc;&#128;&#147; one that\n        says what experience is and what type of physical systems can\n        have it. Giulio Tononi&acirc;&#128;&#153;s Integrated Information Theory (IIT)\n        does so by starting from conscious experience itself via five\n        phenomenological axioms of existence, composition, information,\n        integration, and exclusion. From these it derives five\n        postulates about the properties required of physical mechanisms\n        to support consciousness. The theory provides a principled\n        account of both the quantity and the quality of an individual\n        experience, and a calculus to evaluate whether or not a\n        particular system of mechanisms is conscious and of what.\n        Moreover, IIT can explain a range of clinical and laboratory\n        findings, makes a number of testable predictions, and\n        extrapolates to a number of unusual conditions. In sharp\n        contrast with widespread functionalist beliefs, IIT implies that\n        digital computers, even if their behavior were to be\n        functionally equivalent to ours, and even if they were to run\n        faithful simulations of the human brain, would experience next\n        to nothing. <br>\n        <br>\n        Relevant URL: <a moz-do-not-send=\"true\"\n          class=\"moz-txt-link-freetext\"\n          href=\"http://cbmm.mit.edu/events/\">http://cbmm.mit.edu/events/</a>\n        <br>\n        <br>\n        Refreshments to be served immediately after the talk. <br>\n        <br>\n        <a moz-do-not-send=\"true\"\n          href=\"https://calendar.csail.mit.edu/seminar_series/7420\">See\n          other events that are part of the Brains, Minds and Machines\n          Seminar Series September 2015-June 2016.</a>\n        <p><br>\n        </p>\n        <pre class=\"moz-signature\" cols=\"72\">--\nKathleen D. Sullivan\nCenter Manager\nCenter for Brains, Minds and Machines (CBMM)\nMcGovern Institute for Brain Research at MIT\nMassachusetts Institute of Technology\nDepartment of Brain and Cognitive Sciences\nOffice: MIT 46-5169A\nTel.: (617) 253-0551\n</pre>\n        <br>\n      </div>\n      <br>\n      <br>\n    </div>\n    <br>\n  </body>\n</html>','-------- Original Message -------- Subject: Fwd: Talk: Tuesday 09-23-2014 The Integrated Information Theory of Consciousness Date: Mon, 22 Sep 2014 12:20:28 -0400 From: Kathleen Sullivan <kds',1,0,NULL,NULL,NULL,'[\"<54204C4C.1070008@csail.mit.edu>\"]',0,0,NULL,NULL),('º…<∂AOyüFC„ˇKìÎ','2015-05-08 02:33:29','2015-05-08 02:33:29',NULL,2,2,2,'[[\"Tomaso Poggio\", \"tp@ai.mit.edu\"]]','[[\"\", \"csail-announce-bounces@lists.csail.mit.edu\"]]','[]','[[\"\", \"csail-announce@csail.mit.edu\"], [\"\", \"csail-related@csail.mit.edu\"], [\"\", \"csail-all.lists@mit.edu\"]]','[]','[]','\"<54204C4C.1070008@csail.mit.edu>\"','<54205B6D.10308@ai.mit.edu>','Fwd: Fwd: Talk: Tuesday 09-23-2014 The Integrated Information Theory	of Consciousness','2014-09-22 17:25:46',16089,'b2baa4d84975bc4a340496bca4327b74fd36f66cb8c9d03985e99fed9e185125',0,0,0,NULL,'<html>\n  <head>\n\n    <meta http-equiv=\"content-type\" content=\"text/html; charset=ISO-8859-1\">\n  </head>\n  <body bgcolor=\"#FFFFFF\" text=\"#000000\">\n    <br>\n    <div class=\"moz-forward-container\"><br>\n      <br>\n      -------- Original Message --------\n      <table class=\"moz-email-headers-table\" border=\"0\" cellpadding=\"0\"\n        cellspacing=\"0\">\n        <tbody>\n          <tr>\n            <th align=\"RIGHT\" nowrap=\"nowrap\" valign=\"BASELINE\">Subject:\n            </th>\n            <td>Fwd: Talk: Tuesday 09-23-2014 The Integrated Information\n              Theory of Consciousness</td>\n          </tr>\n          <tr>\n            <th align=\"RIGHT\" nowrap=\"nowrap\" valign=\"BASELINE\">Date: </th>\n            <td>Mon, 22 Sep 2014 12:20:28 -0400</td>\n          </tr>\n          <tr>\n            <th align=\"RIGHT\" nowrap=\"nowrap\" valign=\"BASELINE\">From: </th>\n            <td>Kathleen Sullivan <a class=\"moz-txt-link-rfc2396E\" href=\"mailto:kdsulliv@csail.mit.edu\">&lt;kdsulliv@csail.mit.edu&gt;</a></td>\n          </tr>\n          <tr>\n            <th align=\"RIGHT\" nowrap=\"nowrap\" valign=\"BASELINE\">To: </th>\n            <td><a class=\"moz-txt-link-abbreviated\" href=\"mailto:bcs-all@mit.edu\">bcs-all@mit.edu</a> <a class=\"moz-txt-link-rfc2396E\" href=\"mailto:bcs-all@mit.edu\">&lt;bcs-all@mit.edu&gt;</a></td>\n          </tr>\n        </tbody>\n      </table>\n      <br>\n      <br>\n      <meta http-equiv=\"content-type\" content=\"text/html;\n        charset=ISO-8859-1\">\n      <b>Brains, Minds and Machines Seminar Series </b><br>\n      <div class=\"moz-forward-container\">\n        <h2>The Integrated Information Theory of Consciousness</h2>\n        Speaker: Dr. Christof Koch, Chief Scientific Officer, Allen\n        Institute for Brain Science <br>\n        Date: Tuesday, September 23, 2014 <br>\n        Time: 4:00 PM<br>\n        Location: Singleton Auditorium, MIT 46-3002, 43 Vassar St.,\n        Cambridge MA<br>\n        Host: Prof. Tomaso Poggio, Director CBMM<br>\n        <br>\n        Abstract:&Acirc;&nbsp; The science of consciousness has made great strides\n        by focusing on the behavioral and neuronal correlates of\n        experience. However, such correlates are not enough if we are to\n        understand even basic facts, for example, why the cerebral\n        cortex gives rise to consciousness but the cerebellum does not,\n        though it has even more neurons and appears to be just as\n        complicated. Moreover, correlates are of little help in many\n        instances where we would like to know if consciousness is\n        present: patients with a few remaining islands of functioning\n        cortex, pre-term infants, non-mammalian species, and machines\n        that are rapidly outperforming people at driving, recognizing\n        faces and objects, and answering difficult questions. To address\n        these issues, we need a theory of consciousness &acirc;&#128;&#147; one that\n        says what experience is and what type of physical systems can\n        have it. Giulio Tononi&acirc;&#128;&#153;s Integrated Information Theory (IIT)\n        does so by starting from conscious experience itself via five\n        phenomenological axioms of existence, composition, information,\n        integration, and exclusion. From these it derives five\n        postulates about the properties required of physical mechanisms\n        to support consciousness. The theory provides a principled\n        account of both the quantity and the quality of an individual\n        experience, and a calculus to evaluate whether or not a\n        particular system of mechanisms is conscious and of what.\n        Moreover, IIT can explain a range of clinical and laboratory\n        findings, makes a number of testable predictions, and\n        extrapolates to a number of unusual conditions. In sharp\n        contrast with widespread functionalist beliefs, IIT implies that\n        digital computers, even if their behavior were to be\n        functionally equivalent to ours, and even if they were to run\n        faithful simulations of the human brain, would experience next\n        to nothing. <br>\n        <br>\n        Relevant URL: <a moz-do-not-send=\"true\"\n          class=\"moz-txt-link-freetext\"\n          href=\"http://cbmm.mit.edu/events/\">http://cbmm.mit.edu/events/</a>\n        <br>\n        <br>\n        Refreshments to be served immediately after the talk. <br>\n        <br>\n        <a moz-do-not-send=\"true\"\n          href=\"https://calendar.csail.mit.edu/seminar_series/7420\">See\n          other events that are part of the Brains, Minds and Machines\n          Seminar Series September 2015-June 2016.</a>\n        <p><br>\n        </p>\n        <pre class=\"moz-signature\" cols=\"72\">--\nKathleen D. Sullivan\nCenter Manager\nCenter for Brains, Minds and Machines (CBMM)\nMcGovern Institute for Brain Research at MIT\nMassachusetts Institute of Technology\nDepartment of Brain and Cognitive Sciences\nOffice: MIT 46-5169A\nTel.: (617) 253-0551\n</pre>\n        <br>\n      </div>\n      <br>\n      <br>\n    </div>\n    <br>\n  </body>\n</html>','-------- Original Message -------- Subject: Fwd: Talk: Tuesday 09-23-2014 The Integrated Information Theory of Consciousness Date: Mon, 22 Sep 2014 12:20:28 -0400 From: Kathleen Sullivan <kds',6,0,NULL,NULL,NULL,'[\"<54204C4C.1070008@csail.mit.edu>\"]',0,0,NULL,NULL);
/*!40000 ALTER TABLE `message` ENABLE KEYS */;
UNLOCK TABLES;

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
  KEY `ix_messagecontactassociation_deleted_at` (`deleted_at`),
  KEY `ix_messagecontactassociation_updated_at` (`updated_at`),
  CONSTRAINT `messagecontactassociation_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`id`) ON DELETE CASCADE,
  CONSTRAINT `messagecontactassociation_ibfk_2` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `messagecontactassociation`
--

LOCK TABLES `messagecontactassociation` WRITE;
/*!40000 ALTER TABLE `messagecontactassociation` DISABLE KEYS */;
/*!40000 ALTER TABLE `messagecontactassociation` ENABLE KEYS */;
UNLOCK TABLES;

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
  KEY `ix_namespace_public_id` (`public_id`),
  KEY `ix_namespace_deleted_at` (`deleted_at`),
  KEY `ix_namespace_created_at` (`created_at`),
  CONSTRAINT `namespace_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `namespace`
--

LOCK TABLES `namespace` WRITE;
/*!40000 ALTER TABLE `namespace` DISABLE KEYS */;
INSERT INTO `namespace` VALUES ('≈‘jjg,DÇ¥wH¸gK6Ä','2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,1,1,'root'),('ø)ÿg‰O7Æ·(‘QÊ','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,2,2,'root');
/*!40000 ALTER TABLE `namespace` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `outlookaccount`
--

DROP TABLE IF EXISTS `outlookaccount`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `outlookaccount` (
  `id` int(11) NOT NULL,
  `client_id` varchar(256) DEFAULT NULL,
  `client_secret` varchar(256) DEFAULT NULL,
  `scope` varchar(512) DEFAULT NULL,
  `family_name` varchar(256) DEFAULT NULL,
  `given_name` varchar(256) DEFAULT NULL,
  `gender` varchar(16) DEFAULT NULL,
  `o_id` varchar(32) DEFAULT NULL,
  `o_id_token` varchar(1024) DEFAULT NULL,
  `link` varchar(256) DEFAULT NULL,
  `locale` varchar(8) DEFAULT NULL,
  `refresh_token_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `refresh_token_id` (`refresh_token_id`),
  CONSTRAINT `outlookaccount_ibfk_1` FOREIGN KEY (`id`) REFERENCES `imapaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `outlookaccount_ibfk_2` FOREIGN KEY (`refresh_token_id`) REFERENCES `secret` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `outlookaccount`
--

LOCK TABLES `outlookaccount` WRITE;
/*!40000 ALTER TABLE `outlookaccount` DISABLE KEYS */;
/*!40000 ALTER TABLE `outlookaccount` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `part`
--

DROP TABLE IF EXISTS `part`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `part` (
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `block_id` int(11) DEFAULT NULL,
  `message_id` int(11) DEFAULT NULL,
  `walk_index` int(11) DEFAULT NULL,
  `content_disposition` enum('inline','attachment') DEFAULT NULL,
  `content_id` varchar(255) DEFAULT NULL,
  `is_inboxapp_attachment` tinyint(1) DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `message_id` (`message_id`,`walk_index`),
  KEY `block_id` (`block_id`),
  KEY `ix_part_created_at` (`created_at`),
  KEY `ix_part_deleted_at` (`deleted_at`),
  KEY `ix_part_updated_at` (`updated_at`),
  CONSTRAINT `part_ibfk_1` FOREIGN KEY (`block_id`) REFERENCES `block` (`id`) ON DELETE CASCADE,
  CONSTRAINT `part_ibfk_2` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `part`
--

LOCK TABLES `part` WRITE;
/*!40000 ALTER TABLE `part` DISABLE KEYS */;
INSERT INTO `part` VALUES ('2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,1,2,1,0,NULL,NULL,0),('2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,2,3,1,2,NULL,NULL,0),('2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,3,4,1,3,NULL,NULL,0),('2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,4,5,1,4,'attachment',NULL,0),('2015-05-08 02:33:29','2015-05-08 02:33:29',NULL,5,7,2,0,NULL,NULL,0),('2015-05-08 02:33:29','2015-05-08 02:33:29',NULL,6,8,2,2,NULL,NULL,0),('2015-05-08 02:33:29','2015-05-08 02:33:29',NULL,7,9,2,3,NULL,NULL,0),('2015-05-08 02:33:29','2015-05-08 02:33:29',NULL,8,10,2,4,'attachment',NULL,0);
/*!40000 ALTER TABLE `part` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `recurringevent`
--

DROP TABLE IF EXISTS `recurringevent`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `recurringevent` (
  `id` int(11) NOT NULL,
  `rrule` varchar(255) DEFAULT NULL,
  `exdate` text,
  `until` datetime DEFAULT NULL,
  `start_timezone` varchar(35) DEFAULT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `recurringevent_ibfk_1` FOREIGN KEY (`id`) REFERENCES `event` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `recurringevent`
--

LOCK TABLES `recurringevent` WRITE;
/*!40000 ALTER TABLE `recurringevent` DISABLE KEYS */;
/*!40000 ALTER TABLE `recurringevent` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `recurringeventoverride`
--

DROP TABLE IF EXISTS `recurringeventoverride`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `recurringeventoverride` (
  `id` int(11) NOT NULL,
  `master_event_id` int(11) DEFAULT NULL,
  `master_event_uid` varchar(767) CHARACTER SET ascii DEFAULT NULL,
  `original_start_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `master_event_id` (`master_event_id`),
  KEY `ix_recurringeventoverride_master_event_uid` (`master_event_uid`),
  CONSTRAINT `recurringeventoverride_ibfk_1` FOREIGN KEY (`id`) REFERENCES `event` (`id`) ON DELETE CASCADE,
  CONSTRAINT `recurringeventoverride_ibfk_2` FOREIGN KEY (`master_event_id`) REFERENCES `event` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `recurringeventoverride`
--

LOCK TABLES `recurringeventoverride` WRITE;
/*!40000 ALTER TABLE `recurringeventoverride` DISABLE KEYS */;
/*!40000 ALTER TABLE `recurringeventoverride` ENABLE KEYS */;
UNLOCK TABLES;

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
  KEY `ix_searchindexcursor_deleted_at` (`deleted_at`),
  KEY `ix_searchindexcursor_created_at` (`created_at`),
  KEY `ix_searchindexcursor_transaction_id` (`transaction_id`),
  KEY `ix_searchindexcursor_updated_at` (`updated_at`),
  CONSTRAINT `searchindexcursor_ibfk_1` FOREIGN KEY (`transaction_id`) REFERENCES `transaction` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `searchindexcursor`
--

LOCK TABLES `searchindexcursor` WRITE;
/*!40000 ALTER TABLE `searchindexcursor` DISABLE KEYS */;
/*!40000 ALTER TABLE `searchindexcursor` ENABLE KEYS */;
UNLOCK TABLES;

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
  `_secret` blob NOT NULL,
  `type` enum('password','token') NOT NULL,
  `encryption_scheme` int(11) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `ix_secret_created_at` (`created_at`),
  KEY `ix_secret_updated_at` (`updated_at`),
  KEY `ix_secret_deleted_at` (`deleted_at`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `secret`
--

LOCK TABLES `secret` WRITE;
/*!40000 ALTER TABLE `secret` DISABLE KEYS */;
INSERT INTO `secret` VALUES ('2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,1,'1/eo6XNHwo4dMOQa3yOtR6S4yd9bR-vxhn74APr59j1LsMEudVrK5jSpoR30zcRFq6','token',0);
/*!40000 ALTER TABLE `secret` ENABLE KEYS */;
UNLOCK TABLES;

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
) ENGINE=InnoDB AUTO_INCREMENT=23 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tag`
--

LOCK TABLES `tag` WRITE;
/*!40000 ALTER TABLE `tag` DISABLE KEYS */;
INSERT INTO `tag` VALUES ('2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,1,1,'sending','sending',0),('2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,2,1,'unread','unread',0),('2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,3,1,'drafts','drafts',0),('2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,4,1,'spam','spam',0),('2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,5,1,'inbox','inbox',0),('2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,6,1,'unseen','unseen',0),('2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,7,1,'starred','starred',0),('2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,8,1,'trash','trash',0),('2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,9,1,'archive','archive',0),('2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,10,1,'sent','sent',0),('2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,11,1,'attachment','attachment',0),('2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,12,2,'sending','sending',0),('2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,13,2,'unread','unread',0),('2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,14,2,'drafts','drafts',0),('2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,15,2,'spam','spam',0),('2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,16,2,'inbox','inbox',0),('2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,17,2,'unseen','unseen',0),('2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,18,2,'starred','starred',0),('2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,19,2,'trash','trash',0),('2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,20,2,'archive','archive',0),('2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,21,2,'sent','sent',0),('2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,22,2,'attachment','attachment',0);
/*!40000 ALTER TABLE `tag` ENABLE KEYS */;
UNLOCK TABLES;

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
  KEY `tag_id` (`tag_id`),
  KEY `ix_tagitem_deleted_at` (`deleted_at`),
  KEY `ix_tagitem_created_at` (`created_at`),
  KEY `tag_thread_ids` (`thread_id`,`tag_id`),
  KEY `ix_tagitem_updated_at` (`updated_at`),
  CONSTRAINT `tagitem_ibfk_1` FOREIGN KEY (`thread_id`) REFERENCES `thread` (`id`) ON DELETE CASCADE,
  CONSTRAINT `tagitem_ibfk_2` FOREIGN KEY (`tag_id`) REFERENCES `tag` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tagitem`
--

LOCK TABLES `tagitem` WRITE;
/*!40000 ALTER TABLE `tagitem` DISABLE KEYS */;
INSERT INTO `tagitem` VALUES ('2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,1,1,11),('2015-05-08 02:33:29','2015-05-08 02:33:29',NULL,2,2,22);
/*!40000 ALTER TABLE `tagitem` ENABLE KEYS */;
UNLOCK TABLES;

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
  `_cleaned_subject` varchar(255) DEFAULT NULL,
  `subjectdate` datetime NOT NULL,
  `recentdate` datetime NOT NULL,
  `snippet` varchar(191) DEFAULT NULL,
  `version` int(11) DEFAULT '0',
  `namespace_id` int(11) NOT NULL,
  `type` varchar(16) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_cleaned_subject` (`_cleaned_subject`(191)),
  KEY `ix_thread_subjectdate` (`subjectdate`),
  KEY `ix_thread_namespace_id_recentdate_deleted_at` (`namespace_id`,`recentdate`,`deleted_at`),
  KEY `ix_thread_public_id` (`public_id`),
  KEY `ix_thread_namespace_id` (`namespace_id`),
  KEY `ix_thread_deleted_at` (`deleted_at`),
  KEY `ix_thread_recentdate` (`recentdate`),
  KEY `ix_thread_created_at` (`created_at`),
  KEY `ix_thread_subject` (`subject`(191)),
  KEY `ix_thread_updated_at` (`updated_at`),
  CONSTRAINT `thread_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `thread`
--

LOCK TABLES `thread` WRITE;
/*!40000 ALTER TABLE `thread` DISABLE KEYS */;
INSERT INTO `thread` VALUES ('Ä,CNùÂK(à‘˝ÅcÆÆÉ','2015-05-08 02:33:25','2015-05-08 02:33:27',NULL,1,'Fwd: Fwd: Talk: Tuesday 09-23-2014 The Integrated Information Theory	of Consciousness','Talk: Tuesday 09-23-2014 The Integrated Information Theory	of Consciousness','2014-09-22 17:25:46','2015-05-08 02:33:25','',1,1,NULL),(',i|}N’ï¬ú÷ÀÏ5','2015-05-08 02:33:27','2015-05-08 02:33:29',NULL,2,'Fwd: Fwd: Talk: Tuesday 09-23-2014 The Integrated Information Theory	of Consciousness','Talk: Tuesday 09-23-2014 The Integrated Information Theory	of Consciousness','2014-09-22 17:25:46','2015-05-08 02:33:27','',1,2,NULL);
/*!40000 ALTER TABLE `thread` ENABLE KEYS */;
UNLOCK TABLES;

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
  `namespace_id` int(11) NOT NULL,
  `object_type` varchar(20) NOT NULL,
  `record_id` int(11) NOT NULL,
  `object_public_id` varchar(191) NOT NULL,
  `command` enum('insert','update','delete') NOT NULL,
  `snapshot` longtext,
  PRIMARY KEY (`id`),
  KEY `ix_transaction_object_public_id` (`object_public_id`),
  KEY `ix_transaction_deleted_at` (`deleted_at`),
  KEY `object_type_record_id` (`object_type`,`record_id`),
  KEY `ix_transaction_record_id` (`record_id`),
  KEY `namespace_id_deleted_at` (`namespace_id`,`deleted_at`),
  KEY `ix_transaction_public_id` (`public_id`),
  KEY `ix_transaction_updated_at` (`updated_at`),
  KEY `namespace_id_created_at` (`namespace_id`,`created_at`),
  KEY `ix_transaction_object_type` (`object_type`),
  KEY `ix_transaction_created_at` (`created_at`),
  CONSTRAINT `transaction_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=31 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `transaction`
--

LOCK TABLES `transaction` WRITE;
/*!40000 ALTER TABLE `transaction` DISABLE KEYS */;
INSERT INTO `transaction` VALUES ('°⁄	RH)C5ôÆ 13j›i','2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,1,1,'tag',1,'sending','insert','{\"readonly\": true, \"object\": \"tag\", \"namespace_id\": \"bpmr2ggs3r5cavprnpk92rnnk\", \"id\": \"sending\", \"name\": \"sending\"}'),('R?*C¡Jõ≥íUãπÿ','2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,2,1,'tag',2,'unread','insert','{\"readonly\": false, \"object\": \"tag\", \"namespace_id\": \"bpmr2ggs3r5cavprnpk92rnnk\", \"id\": \"unread\", \"name\": \"unread\"}'),('‘8¶¡o{Jû¥°\rìÄ°©','2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,3,1,'tag',9,'archive','insert','{\"readonly\": false, \"object\": \"tag\", \"namespace_id\": \"bpmr2ggs3r5cavprnpk92rnnk\", \"id\": \"archive\", \"name\": \"archive\"}'),('Ü≤≠¡¬√L¬ü‹±›©Á','2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,4,1,'tag',10,'sent','insert','{\"readonly\": true, \"object\": \"tag\", \"namespace_id\": \"bpmr2ggs3r5cavprnpk92rnnk\", \"id\": \"sent\", \"name\": \"sent\"}'),('K*L≥•ÁDSò†º°ÿ’b','2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,5,1,'tag',3,'drafts','insert','{\"readonly\": true, \"object\": \"tag\", \"namespace_id\": \"bpmr2ggs3r5cavprnpk92rnnk\", \"id\": \"drafts\", \"name\": \"drafts\"}'),('—Q3UhtLz™ñA0_QR','2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,6,1,'tag',4,'spam','insert','{\"readonly\": false, \"object\": \"tag\", \"namespace_id\": \"bpmr2ggs3r5cavprnpk92rnnk\", \"id\": \"spam\", \"name\": \"spam\"}'),('MOºGÅœ@*®ÉR∏m>6','2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,7,1,'tag',5,'inbox','insert','{\"readonly\": false, \"object\": \"tag\", \"namespace_id\": \"bpmr2ggs3r5cavprnpk92rnnk\", \"id\": \"inbox\", \"name\": \"inbox\"}'),('©ˆÎ¡±JP¢ Fö}«Ñ','2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,8,1,'calendar',1,'1n09w4glozlv55n6pcxwz428e','insert','{\"read_only\": true, \"namespace_id\": \"bpmr2ggs3r5cavprnpk92rnnk\", \"name\": \"Emailed events\", \"object\": \"calendar\", \"id\": \"1n09w4glozlv55n6pcxwz428e\", \"description\": \"Emailed events\"}'),('t≈äÖﬁ˝Iwë‰j⁄ÂJ0','2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,9,1,'tag',11,'attachment','insert','{\"readonly\": true, \"object\": \"tag\", \"namespace_id\": \"bpmr2ggs3r5cavprnpk92rnnk\", \"id\": \"attachment\", \"name\": \"attachment\"}'),('$	ÒáØM∏µ§€â†◊?','2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,10,1,'tag',8,'trash','insert','{\"readonly\": false, \"object\": \"tag\", \"namespace_id\": \"bpmr2ggs3r5cavprnpk92rnnk\", \"id\": \"trash\", \"name\": \"trash\"}'),('Ï8D¨Ã@:µıúÁ_hØ','2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,11,1,'tag',6,'unseen','insert','{\"readonly\": false, \"object\": \"tag\", \"namespace_id\": \"bpmr2ggs3r5cavprnpk92rnnk\", \"id\": \"unseen\", \"name\": \"unseen\"}'),('«YÙ#ı®Etâa]–.o$í','2015-05-08 02:11:36','2015-05-08 02:11:36',NULL,12,1,'tag',7,'starred','insert','{\"readonly\": false, \"object\": \"tag\", \"namespace_id\": \"bpmr2ggs3r5cavprnpk92rnnk\", \"id\": \"starred\", \"name\": \"starred\"}'),('K\0‡‚\"¿BTùè\Z√‹Nπ—','2015-05-08 02:33:26','2015-05-08 02:33:26',NULL,13,1,'thread',1,'7l68jfz8h07litq0e8yeopz7n','insert','{\"namespace_id\": \"bpmr2ggs3r5cavprnpk92rnnk\", \"tags\": [], \"last_message_timestamp\": {\"$date\": 1431052405982}, \"object\": \"thread\", \"id\": \"7l68jfz8h07litq0e8yeopz7n\", \"snippet\": \"\", \"participants\": [], \"version\": 0, \"first_message_timestamp\": {\"$date\": 1431052405982}, \"draft_ids\": [], \"message_ids\": [], \"subject\": null}'),('nw∫¡«ItßtZõ≈§Ë','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,14,1,'message',1,'99gp6b5ugeglhef3rcg2506v8','insert','{\"body\": \"<html>\\n  <head>\\n\\n    <meta http-equiv=\\\"content-type\\\" content=\\\"text/html; charset=ISO-8859-1\\\">\\n  </head>\\n  <body bgcolor=\\\"#FFFFFF\\\" text=\\\"#000000\\\">\\n    <br>\\n    <div class=\\\"moz-forward-container\\\"><br>\\n      <br>\\n      -------- Original Message --------\\n      <table class=\\\"moz-email-headers-table\\\" border=\\\"0\\\" cellpadding=\\\"0\\\"\\n        cellspacing=\\\"0\\\">\\n        <tbody>\\n          <tr>\\n            <th align=\\\"RIGHT\\\" nowrap=\\\"nowrap\\\" valign=\\\"BASELINE\\\">Subject:\\n            </th>\\n            <td>Fwd: Talk: Tuesday 09-23-2014 The Integrated Information\\n              Theory of Consciousness</td>\\n          </tr>\\n          <tr>\\n            <th align=\\\"RIGHT\\\" nowrap=\\\"nowrap\\\" valign=\\\"BASELINE\\\">Date: </th>\\n            <td>Mon, 22 Sep 2014 12:20:28 -0400</td>\\n          </tr>\\n          <tr>\\n            <th align=\\\"RIGHT\\\" nowrap=\\\"nowrap\\\" valign=\\\"BASELINE\\\">From: </th>\\n            <td>Kathleen Sullivan <a class=\\\"moz-txt-link-rfc2396E\\\" href=\\\"mailto:kdsulliv@csail.mit.edu\\\">&lt;kdsulliv@csail.mit.edu&gt;</a></td>\\n          </tr>\\n          <tr>\\n            <th align=\\\"RIGHT\\\" nowrap=\\\"nowrap\\\" valign=\\\"BASELINE\\\">To: </th>\\n            <td><a class=\\\"moz-txt-link-abbreviated\\\" href=\\\"mailto:bcs-all@mit.edu\\\">bcs-all@mit.edu</a> <a class=\\\"moz-txt-link-rfc2396E\\\" href=\\\"mailto:bcs-all@mit.edu\\\">&lt;bcs-all@mit.edu&gt;</a></td>\\n          </tr>\\n        </tbody>\\n      </table>\\n      <br>\\n      <br>\\n      <meta http-equiv=\\\"content-type\\\" content=\\\"text/html;\\n        charset=ISO-8859-1\\\">\\n      <b>Brains, Minds and Machines Seminar Series </b><br>\\n      <div class=\\\"moz-forward-container\\\">\\n        <h2>The Integrated Information Theory of Consciousness</h2>\\n        Speaker: Dr. Christof Koch, Chief Scientific Officer, Allen\\n        Institute for Brain Science <br>\\n        Date: Tuesday, September 23, 2014 <br>\\n        Time: 4:00 PM<br>\\n        Location: Singleton Auditorium, MIT 46-3002, 43 Vassar St.,\\n        Cambridge MA<br>\\n        Host: Prof. Tomaso Poggio, Director CBMM<br>\\n        <br>\\n        Abstract:&Acirc;&nbsp; The science of consciousness has made great strides\\n        by focusing on the behavioral and neuronal correlates of\\n        experience. However, such correlates are not enough if we are to\\n        understand even basic facts, for example, why the cerebral\\n        cortex gives rise to consciousness but the cerebellum does not,\\n        though it has even more neurons and appears to be just as\\n        complicated. Moreover, correlates are of little help in many\\n        instances where we would like to know if consciousness is\\n        present: patients with a few remaining islands of functioning\\n        cortex, pre-term infants, non-mammalian species, and machines\\n        that are rapidly outperforming people at driving, recognizing\\n        faces and objects, and answering difficult questions. To address\\n        these issues, we need a theory of consciousness &acirc;&#128;&#147; one that\\n        says what experience is and what type of physical systems can\\n        have it. Giulio Tononi&acirc;&#128;&#153;s Integrated Information Theory (IIT)\\n        does so by starting from conscious experience itself via five\\n        phenomenological axioms of existence, composition, information,\\n        integration, and exclusion. From these it derives five\\n        postulates about the properties required of physical mechanisms\\n        to support consciousness. The theory provides a principled\\n        account of both the quantity and the quality of an individual\\n        experience, and a calculus to evaluate whether or not a\\n        particular system of mechanisms is conscious and of what.\\n        Moreover, IIT can explain a range of clinical and laboratory\\n        findings, makes a number of testable predictions, and\\n        extrapolates to a number of unusual conditions. In sharp\\n        contrast with widespread functionalist beliefs, IIT implies that\\n        digital computers, even if their behavior were to be\\n        functionally equivalent to ours, and even if they were to run\\n        faithful simulations of the human brain, would experience next\\n        to nothing. <br>\\n        <br>\\n        Relevant URL: <a moz-do-not-send=\\\"true\\\"\\n          class=\\\"moz-txt-link-freetext\\\"\\n          href=\\\"http://cbmm.mit.edu/events/\\\">http://cbmm.mit.edu/events/</a>\\n        <br>\\n        <br>\\n        Refreshments to be served immediately after the talk. <br>\\n        <br>\\n        <a moz-do-not-send=\\\"true\\\"\\n          href=\\\"https://calendar.csail.mit.edu/seminar_series/7420\\\">See\\n          other events that are part of the Brains, Minds and Machines\\n          Seminar Series September 2015-June 2016.</a>\\n        <p><br>\\n        </p>\\n        <pre class=\\\"moz-signature\\\" cols=\\\"72\\\">--\\nKathleen D. Sullivan\\nCenter Manager\\nCenter for Brains, Minds and Machines (CBMM)\\nMcGovern Institute for Brain Research at MIT\\nMassachusetts Institute of Technology\\nDepartment of Brain and Cognitive Sciences\\nOffice: MIT 46-5169A\\nTel.: (617) 253-0551\\n</pre>\\n        <br>\\n      </div>\\n      <br>\\n      <br>\\n    </div>\\n    <br>\\n  </body>\\n</html>\", \"files\": [{\"size\": 134, \"id\": \"31ko4icvbgfdugoxj1ozsdtxc\", \"content_type\": \"text/plain\", \"filename\": \"Attached Message Part\"}], \"namespace_id\": \"bpmr2ggs3r5cavprnpk92rnnk\", \"from\": [{\"name\": \"Tomaso Poggio\", \"email\": \"tp@ai.mit.edu\"}], \"to\": [{\"name\": \"\", \"email\": \"csail-announce@csail.mit.edu\"}, {\"name\": \"\", \"email\": \"csail-related@csail.mit.edu\"}, {\"name\": \"\", \"email\": \"csail-all.lists@mit.edu\"}], \"cc\": [], \"id\": \"99gp6b5ugeglhef3rcg2506v8\", \"object\": \"message\", \"bcc\": [], \"snippet\": \"-------- Original Message -------- Subject: Fwd: Talk: Tuesday 09-23-2014 The Integrated Information Theory of Consciousness Date: Mon, 22 Sep 2014 12:20:28 -0400 From: Kathleen Sullivan <kds\", \"thread_id\": \"7l68jfz8h07litq0e8yeopz7n\", \"reply_to\": [], \"date\": {\"$date\": 1411406746000}, \"unread\": true, \"events\": [], \"subject\": \"Fwd: Fwd: Talk: Tuesday 09-23-2014 The Integrated Information Theory\\tof Consciousness\"}'),('!)∂—ÄNH÷ÉJ—/˚◊‡','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,15,1,'thread',1,'7l68jfz8h07litq0e8yeopz7n','update','{\"namespace_id\": \"bpmr2ggs3r5cavprnpk92rnnk\", \"tags\": [{\"name\": \"attachment\", \"id\": \"attachment\"}], \"last_message_timestamp\": {\"$date\": 1431052405000}, \"object\": \"thread\", \"id\": \"7l68jfz8h07litq0e8yeopz7n\", \"snippet\": \"\", \"participants\": [{\"name\": \"Tomaso Poggio\", \"email\": \"tp@ai.mit.edu\"}, {\"name\": \"\", \"email\": \"csail-announce@csail.mit.edu\"}, {\"name\": \"\", \"email\": \"csail-all.lists@mit.edu\"}, {\"name\": \"\", \"email\": \"csail-related@csail.mit.edu\"}], \"version\": 1, \"first_message_timestamp\": {\"$date\": 1411406746000}, \"draft_ids\": [], \"message_ids\": [\"99gp6b5ugeglhef3rcg2506v8\", \"99gp6b5ugeglhef3rcg2506v8\"], \"subject\": \"Fwd: Fwd: Talk: Tuesday 09-23-2014 The Integrated Information Theory\\tof Consciousness\"}'),('`·¡ËF*õÚ	O','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,16,2,'tag',18,'starred','insert','{\"readonly\": false, \"object\": \"tag\", \"namespace_id\": \"bb7vh7lyv6rnycoa9hxuq4i5i\", \"id\": \"starred\", \"name\": \"starred\"}'),('TD4∑FnµSÎ]Ïê4»','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,17,2,'tag',22,'attachment','insert','{\"readonly\": true, \"object\": \"tag\", \"namespace_id\": \"bb7vh7lyv6rnycoa9hxuq4i5i\", \"id\": \"attachment\", \"name\": \"attachment\"}'),('Oè‘ØÀíL>Ωw∏5\ràt','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,18,2,'tag',13,'unread','insert','{\"readonly\": false, \"object\": \"tag\", \"namespace_id\": \"bb7vh7lyv6rnycoa9hxuq4i5i\", \"id\": \"unread\", \"name\": \"unread\"}'),('Twé©‘!OùH≠ƒË~d','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,19,2,'tag',17,'unseen','insert','{\"readonly\": false, \"object\": \"tag\", \"namespace_id\": \"bb7vh7lyv6rnycoa9hxuq4i5i\", \"id\": \"unseen\", \"name\": \"unseen\"}'),('£9¨-bIé\r	≈DY±O','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,20,2,'tag',12,'sending','insert','{\"readonly\": true, \"object\": \"tag\", \"namespace_id\": \"bb7vh7lyv6rnycoa9hxuq4i5i\", \"id\": \"sending\", \"name\": \"sending\"}'),('Iˆ{ÌæL#£âÔ”»a','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,21,2,'tag',16,'inbox','insert','{\"readonly\": false, \"object\": \"tag\", \"namespace_id\": \"bb7vh7lyv6rnycoa9hxuq4i5i\", \"id\": \"inbox\", \"name\": \"inbox\"}'),('´ZoLòCÇÅ£Q%$¬µ','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,22,2,'tag',21,'sent','insert','{\"readonly\": true, \"object\": \"tag\", \"namespace_id\": \"bb7vh7lyv6rnycoa9hxuq4i5i\", \"id\": \"sent\", \"name\": \"sent\"}'),('ì≤d–meB7ïÎWL4¶u(','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,23,2,'calendar',2,'2sp18lz18zxni533rzfu8o7mn','insert','{\"read_only\": true, \"namespace_id\": \"bb7vh7lyv6rnycoa9hxuq4i5i\", \"name\": \"Emailed events\", \"object\": \"calendar\", \"id\": \"2sp18lz18zxni533rzfu8o7mn\", \"description\": \"Emailed events\"}'),('+π≥z„9Jﬁ¢2fÁh\'s—','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,24,2,'tag',15,'spam','insert','{\"readonly\": false, \"object\": \"tag\", \"namespace_id\": \"bb7vh7lyv6rnycoa9hxuq4i5i\", \"id\": \"spam\", \"name\": \"spam\"}'),('ô€ûjM¸H“î›Y·Í™∫','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,25,2,'tag',20,'archive','insert','{\"readonly\": false, \"object\": \"tag\", \"namespace_id\": \"bb7vh7lyv6rnycoa9hxuq4i5i\", \"id\": \"archive\", \"name\": \"archive\"}'),(' æN¨P⁄F	Ç+Ó„ã∏','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,26,2,'tag',14,'drafts','insert','{\"readonly\": true, \"object\": \"tag\", \"namespace_id\": \"bb7vh7lyv6rnycoa9hxuq4i5i\", \"id\": \"drafts\", \"name\": \"drafts\"}'),('d?ìSéE«§*<(S¨','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,27,2,'tag',19,'trash','insert','{\"readonly\": false, \"object\": \"tag\", \"namespace_id\": \"bb7vh7lyv6rnycoa9hxuq4i5i\", \"id\": \"trash\", \"name\": \"trash\"}'),(':ÇÀÈcGÆ3Gsí¿∞7','2015-05-08 02:33:27','2015-05-08 02:33:27',NULL,28,2,'thread',2,'4mrhicg4rbg1euiu8i1p4to5','insert','{\"namespace_id\": \"bb7vh7lyv6rnycoa9hxuq4i5i\", \"tags\": [], \"last_message_timestamp\": {\"$date\": 1431052407960}, \"object\": \"thread\", \"id\": \"4mrhicg4rbg1euiu8i1p4to5\", \"snippet\": \"\", \"participants\": [], \"version\": 0, \"first_message_timestamp\": {\"$date\": 1431052407960}, \"draft_ids\": [], \"message_ids\": [], \"subject\": null}'),('.Ifz†	A…§ê∏≈wº«ø','2015-05-08 02:33:29','2015-05-08 02:33:29',NULL,29,2,'message',2,'b6cv3dklqr7lp7antn3fkiwa3','insert','{\"body\": \"<html>\\n  <head>\\n\\n    <meta http-equiv=\\\"content-type\\\" content=\\\"text/html; charset=ISO-8859-1\\\">\\n  </head>\\n  <body bgcolor=\\\"#FFFFFF\\\" text=\\\"#000000\\\">\\n    <br>\\n    <div class=\\\"moz-forward-container\\\"><br>\\n      <br>\\n      -------- Original Message --------\\n      <table class=\\\"moz-email-headers-table\\\" border=\\\"0\\\" cellpadding=\\\"0\\\"\\n        cellspacing=\\\"0\\\">\\n        <tbody>\\n          <tr>\\n            <th align=\\\"RIGHT\\\" nowrap=\\\"nowrap\\\" valign=\\\"BASELINE\\\">Subject:\\n            </th>\\n            <td>Fwd: Talk: Tuesday 09-23-2014 The Integrated Information\\n              Theory of Consciousness</td>\\n          </tr>\\n          <tr>\\n            <th align=\\\"RIGHT\\\" nowrap=\\\"nowrap\\\" valign=\\\"BASELINE\\\">Date: </th>\\n            <td>Mon, 22 Sep 2014 12:20:28 -0400</td>\\n          </tr>\\n          <tr>\\n            <th align=\\\"RIGHT\\\" nowrap=\\\"nowrap\\\" valign=\\\"BASELINE\\\">From: </th>\\n            <td>Kathleen Sullivan <a class=\\\"moz-txt-link-rfc2396E\\\" href=\\\"mailto:kdsulliv@csail.mit.edu\\\">&lt;kdsulliv@csail.mit.edu&gt;</a></td>\\n          </tr>\\n          <tr>\\n            <th align=\\\"RIGHT\\\" nowrap=\\\"nowrap\\\" valign=\\\"BASELINE\\\">To: </th>\\n            <td><a class=\\\"moz-txt-link-abbreviated\\\" href=\\\"mailto:bcs-all@mit.edu\\\">bcs-all@mit.edu</a> <a class=\\\"moz-txt-link-rfc2396E\\\" href=\\\"mailto:bcs-all@mit.edu\\\">&lt;bcs-all@mit.edu&gt;</a></td>\\n          </tr>\\n        </tbody>\\n      </table>\\n      <br>\\n      <br>\\n      <meta http-equiv=\\\"content-type\\\" content=\\\"text/html;\\n        charset=ISO-8859-1\\\">\\n      <b>Brains, Minds and Machines Seminar Series </b><br>\\n      <div class=\\\"moz-forward-container\\\">\\n        <h2>The Integrated Information Theory of Consciousness</h2>\\n        Speaker: Dr. Christof Koch, Chief Scientific Officer, Allen\\n        Institute for Brain Science <br>\\n        Date: Tuesday, September 23, 2014 <br>\\n        Time: 4:00 PM<br>\\n        Location: Singleton Auditorium, MIT 46-3002, 43 Vassar St.,\\n        Cambridge MA<br>\\n        Host: Prof. Tomaso Poggio, Director CBMM<br>\\n        <br>\\n        Abstract:&Acirc;&nbsp; The science of consciousness has made great strides\\n        by focusing on the behavioral and neuronal correlates of\\n        experience. However, such correlates are not enough if we are to\\n        understand even basic facts, for example, why the cerebral\\n        cortex gives rise to consciousness but the cerebellum does not,\\n        though it has even more neurons and appears to be just as\\n        complicated. Moreover, correlates are of little help in many\\n        instances where we would like to know if consciousness is\\n        present: patients with a few remaining islands of functioning\\n        cortex, pre-term infants, non-mammalian species, and machines\\n        that are rapidly outperforming people at driving, recognizing\\n        faces and objects, and answering difficult questions. To address\\n        these issues, we need a theory of consciousness &acirc;&#128;&#147; one that\\n        says what experience is and what type of physical systems can\\n        have it. Giulio Tononi&acirc;&#128;&#153;s Integrated Information Theory (IIT)\\n        does so by starting from conscious experience itself via five\\n        phenomenological axioms of existence, composition, information,\\n        integration, and exclusion. From these it derives five\\n        postulates about the properties required of physical mechanisms\\n        to support consciousness. The theory provides a principled\\n        account of both the quantity and the quality of an individual\\n        experience, and a calculus to evaluate whether or not a\\n        particular system of mechanisms is conscious and of what.\\n        Moreover, IIT can explain a range of clinical and laboratory\\n        findings, makes a number of testable predictions, and\\n        extrapolates to a number of unusual conditions. In sharp\\n        contrast with widespread functionalist beliefs, IIT implies that\\n        digital computers, even if their behavior were to be\\n        functionally equivalent to ours, and even if they were to run\\n        faithful simulations of the human brain, would experience next\\n        to nothing. <br>\\n        <br>\\n        Relevant URL: <a moz-do-not-send=\\\"true\\\"\\n          class=\\\"moz-txt-link-freetext\\\"\\n          href=\\\"http://cbmm.mit.edu/events/\\\">http://cbmm.mit.edu/events/</a>\\n        <br>\\n        <br>\\n        Refreshments to be served immediately after the talk. <br>\\n        <br>\\n        <a moz-do-not-send=\\\"true\\\"\\n          href=\\\"https://calendar.csail.mit.edu/seminar_series/7420\\\">See\\n          other events that are part of the Brains, Minds and Machines\\n          Seminar Series September 2015-June 2016.</a>\\n        <p><br>\\n        </p>\\n        <pre class=\\\"moz-signature\\\" cols=\\\"72\\\">--\\nKathleen D. Sullivan\\nCenter Manager\\nCenter for Brains, Minds and Machines (CBMM)\\nMcGovern Institute for Brain Research at MIT\\nMassachusetts Institute of Technology\\nDepartment of Brain and Cognitive Sciences\\nOffice: MIT 46-5169A\\nTel.: (617) 253-0551\\n</pre>\\n        <br>\\n      </div>\\n      <br>\\n      <br>\\n    </div>\\n    <br>\\n  </body>\\n</html>\", \"files\": [{\"size\": 134, \"id\": \"ad67ztlr0on0ae8wfvhg3hzdn\", \"content_type\": \"text/plain\", \"filename\": \"Attached Message Part\"}], \"namespace_id\": \"bb7vh7lyv6rnycoa9hxuq4i5i\", \"from\": [{\"name\": \"Tomaso Poggio\", \"email\": \"tp@ai.mit.edu\"}], \"to\": [{\"name\": \"\", \"email\": \"csail-announce@csail.mit.edu\"}, {\"name\": \"\", \"email\": \"csail-related@csail.mit.edu\"}, {\"name\": \"\", \"email\": \"csail-all.lists@mit.edu\"}], \"cc\": [], \"id\": \"b6cv3dklqr7lp7antn3fkiwa3\", \"object\": \"message\", \"bcc\": [], \"snippet\": \"-------- Original Message -------- Subject: Fwd: Talk: Tuesday 09-23-2014 The Integrated Information Theory of Consciousness Date: Mon, 22 Sep 2014 12:20:28 -0400 From: Kathleen Sullivan <kds\", \"thread_id\": \"4mrhicg4rbg1euiu8i1p4to5\", \"reply_to\": [], \"date\": {\"$date\": 1411406746000}, \"unread\": true, \"events\": [], \"subject\": \"Fwd: Fwd: Talk: Tuesday 09-23-2014 The Integrated Information Theory\\tof Consciousness\"}'),('CJ∆`/„IÌ≠»á+ıøÈ®','2015-05-08 02:33:29','2015-05-08 02:33:29',NULL,30,2,'thread',2,'4mrhicg4rbg1euiu8i1p4to5','update','{\"namespace_id\": \"bb7vh7lyv6rnycoa9hxuq4i5i\", \"tags\": [{\"name\": \"attachment\", \"id\": \"attachment\"}], \"last_message_timestamp\": {\"$date\": 1431052407000}, \"object\": \"thread\", \"id\": \"4mrhicg4rbg1euiu8i1p4to5\", \"snippet\": \"\", \"participants\": [{\"name\": \"Tomaso Poggio\", \"email\": \"tp@ai.mit.edu\"}, {\"name\": \"\", \"email\": \"csail-announce@csail.mit.edu\"}, {\"name\": \"\", \"email\": \"csail-all.lists@mit.edu\"}, {\"name\": \"\", \"email\": \"csail-related@csail.mit.edu\"}], \"version\": 1, \"first_message_timestamp\": {\"$date\": 1411406746000}, \"draft_ids\": [], \"message_ids\": [\"b6cv3dklqr7lp7antn3fkiwa3\", \"b6cv3dklqr7lp7antn3fkiwa3\"], \"subject\": \"Fwd: Fwd: Talk: Tuesday 09-23-2014 The Integrated Information Theory\\tof Consciousness\"}');
/*!40000 ALTER TABLE `transaction` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2015-05-08  2:34:02
