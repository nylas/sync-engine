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
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `public_id` binary(16) NOT NULL,
  `save_raw_messages` tinyint(1) DEFAULT '1',
  `sync_host` varchar(255) DEFAULT NULL,
  `last_synced_contacts` datetime DEFAULT NULL,
  `type` varchar(16) DEFAULT NULL,
  `inbox_folder_id` int(11) DEFAULT NULL,
  `sent_folder_id` int(11) DEFAULT NULL,
  `drafts_folder_id` int(11) DEFAULT NULL,
  `spam_folder_id` int(11) DEFAULT NULL,
  `trash_folder_id` int(11) DEFAULT NULL,
  `archive_folder_id` int(11) DEFAULT NULL,
  `all_folder_id` int(11) DEFAULT NULL,
  `starred_folder_id` int(11) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `important_folder_id` int(11) DEFAULT NULL,
  `sync_state` enum('running','stopped','killed','invalid','connerror') DEFAULT NULL,
  `_canonicalized_address` varchar(191) DEFAULT NULL,
  `_raw_address` varchar(191) DEFAULT NULL,
  `state` enum('live','down','invalid') DEFAULT NULL,
  `_sync_status` text,
  `last_synced_events` datetime DEFAULT NULL,
  `default_calendar_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_account_public_id` (`public_id`),
  KEY `account_ibfk_2` (`inbox_folder_id`),
  KEY `account_ibfk_3` (`sent_folder_id`),
  KEY `account_ibfk_4` (`drafts_folder_id`),
  KEY `account_ibfk_5` (`spam_folder_id`),
  KEY `account_ibfk_6` (`trash_folder_id`),
  KEY `account_ibfk_7` (`archive_folder_id`),
  KEY `account_ibfk_8` (`all_folder_id`),
  KEY `account_ibfk_9` (`starred_folder_id`),
  KEY `ix_account_created_at` (`created_at`),
  KEY `ix_account_deleted_at` (`deleted_at`),
  KEY `ix_account_updated_at` (`updated_at`),
  KEY `ix_account__canonicalized_address` (`_canonicalized_address`),
  KEY `ix_account__raw_address` (`_raw_address`),
  KEY `default_calendar_ibfk_1` (`default_calendar_id`),
  CONSTRAINT `default_calendar_ibfk_1` FOREIGN KEY (`default_calendar_id`) REFERENCES `calendar` (`id`),
  CONSTRAINT `account_ibfk_2` FOREIGN KEY (`inbox_folder_id`) REFERENCES `folder` (`id`),
  CONSTRAINT `account_ibfk_3` FOREIGN KEY (`sent_folder_id`) REFERENCES `folder` (`id`),
  CONSTRAINT `account_ibfk_4` FOREIGN KEY (`drafts_folder_id`) REFERENCES `folder` (`id`),
  CONSTRAINT `account_ibfk_5` FOREIGN KEY (`spam_folder_id`) REFERENCES `folder` (`id`),
  CONSTRAINT `account_ibfk_6` FOREIGN KEY (`trash_folder_id`) REFERENCES `folder` (`id`),
  CONSTRAINT `account_ibfk_7` FOREIGN KEY (`archive_folder_id`) REFERENCES `folder` (`id`),
  CONSTRAINT `account_ibfk_8` FOREIGN KEY (`all_folder_id`) REFERENCES `folder` (`id`),
  CONSTRAINT `account_ibfk_9` FOREIGN KEY (`starred_folder_id`) REFERENCES `folder` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `account`
--

LOCK TABLES `account` WRITE;
/*!40000 ALTER TABLE `account` DISABLE KEYS */;
INSERT INTO `account` VALUES (1,'ÔøΩÔøΩÔøΩÔøΩhPID',1,'precise64','2014-05-03 01:15:03','gmailaccount',2,4,5,NULL,NULL,NULL,3,NULL,'2014-05-13 02:19:12','2014-08-22 18:02:36',NULL,NULL,NULL,'inboxapptest@gmail.com','inboxapptest@gmail.com',NULL,'{\"sync_start_time\": \"None\", \"sync_end_time\": \"None\"}',NULL,NULL);
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
  `executed` tinyint(1) NOT NULL DEFAULT '0',
  `extra_args` text,
  PRIMARY KEY (`id`),
  KEY `ix_actionlog_created_at` (`created_at`),
  KEY `ix_actionlog_deleted_at` (`deleted_at`),
  KEY `ix_actionlog_namespace_id` (`namespace_id`),
  KEY `ix_actionlog_updated_at` (`updated_at`),
  CONSTRAINT `actionlog_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`)
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
INSERT INTO `alembic_version` VALUES ('1ac03cab7a24');
/*!40000 ALTER TABLE `alembic_version` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `block`
--

DROP TABLE IF EXISTS `block`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `block` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `size` int(11) DEFAULT NULL,
  `data_sha256` varchar(64) DEFAULT NULL,
  `public_id` binary(16) NOT NULL,
  `_content_type_common` enum('text/plain','text/html','multipart/alternative','multipart/mixed','image/jpeg','multipart/related','application/pdf','image/png','image/gif','application/octet-stream','multipart/signed','application/msword','application/pkcs7-signature','message/rfc822','image/jpg') DEFAULT NULL,
  `_content_type_other` varchar(255) DEFAULT NULL,
  `filename` varchar(255) DEFAULT NULL,
  `namespace_id` int(11) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `namespace_id` (`namespace_id`),
  KEY `ix_block_public_id` (`public_id`),
  KEY `ix_block_created_at` (`created_at`),
  KEY `ix_block_deleted_at` (`deleted_at`),
  KEY `ix_block_updated_at` (`updated_at`),
  CONSTRAINT `block_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=51 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `block`
--

LOCK TABLES `block` WRITE;
/*!40000 ALTER TABLE `block` DISABLE KEYS */;
INSERT INTO `block` VALUES (1,1950,'1c61dd2b4dd1193911f3aaa63ac0d7d55058d567664cddaab094e59a46cdc59d','ÔøΩ∆ñKÔøΩÔøΩEÔøΩ',NULL,NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(2,15,'d58d3859935609dd2afe7233c68939cd9cd20ef54e3a61d0442f41fc157fc10d','_ÔøΩÔøΩÔøΩÔøΩÔøΩ','text/plain',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(3,36,'6103eda40adfd98a9e4b4e16ff958e693893f4c37359c76fd9b4e77531a22828','ÔøΩp\ZÔøΩÔøΩÔøΩDÔ','text/html',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(4,6738,'179cd7e3034869737ae02cee0b918fb85f9254ea2fd0c0b3f7b84a32420edebc','v\n  ÔøΩÀíJÔøΩÔøΩ',NULL,NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(5,1361,'7fdc6a5d14d7832747b01287f8b7da14bf612e2e100df9df1b4561bcaec8d268','ÔøΩp}{ÔøΩÔøΩKÔø','text/plain',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(6,2120,'2014eb3bb6de2ecb23151b266a3057be6cf3e9c19659d215b531fcee286a87f5','\nÔøΩÔøΩÔøΩ)0EÔø','text/html',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(7,453,'98ae516cd24a27e52537143ff996e1c462ae2be9ea96ef0df3e4db41f8cb1060','w“™ÔøΩaCÔøΩÔøΩ',NULL,NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(8,1251,'b1558fdb97bc5918be82a7d342358fdd8abaa32cace1c96056319c594af6ddfe','ÔøΩÔøΩÔøΩ3ÔøΩHÔ','text/plain',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(9,12626,'5ef8b7411036839cf82f81125fda1227b56378c14e4d2f2e251aaaa5496062ad','ÔøΩ]ÔøΩpÔøΩ_EÔøΩ','text/html',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(10,2037,'af620f6b1b2178f7ae978e21534b334c1b313e09c1c9657db686726368312434','ÔøΩGXcdÔøΩDÔøΩÔø',NULL,NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(11,3,'98ea6e4f216f2fb4b69fff9b3a44842c38686ca685f3f55dc48c5d3fb1107be4','\\,ÔøΩFÔøΩCZÔøΩ','text/plain',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(12,24,'408ba4f10aada5751a08119a3c82a667239b3094bf14fe2e67a258dc03afbacf','?ÔøΩgÔøΩ@GÔøΩÔø','text/html',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(13,2846,'889b24bb1bf892e1634717a015b0ccd9f93b39afa46a2986be3fe90879d6d19e','ÔøΩ3Ÿò+IŸ¥ÔøΩÔø',NULL,NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(14,13,'004815e57fe5989f9536f2d50d29bcc0474462dfd0543868e43c5351285c4f60','ÔøΩ^”¢ÔøΩbF:ÔøΩÔ','text/plain',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(15,34,'a0d9bb0476a09e0b8cda7c8799e2ff00959e645292dcd64790d9138623393995','ÔøΩÔøΩÔøΩ\'…âGÔø','text/html',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(16,1951,'f582e89b834cd098b5d023d09014c99554e519649523427da7eb6ed1bbb2dbb9','ÔøΩZÀéÔøΩÔøΩGGÔø',NULL,NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(17,14,'b0bbbdfc73c7ebd75b9d5e66896312cc3c3a59fe5c86e0de44de3a132b34ebad','ÔøΩÔøΩk&ÔøΩCŒëÔ','text/plain',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(18,35,'3f93e1bec4711d5bca6c71e1ae3bd7a81437a6ade1e1afab07fd8c26e8f60961','ÔøΩÔøΩ]ÔøΩ~KÔøΩ','text/html',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(19,1965,'223681a017f96b40fa854b8810c039a20db392c8df9773575177976aba3e0834','ÔøΩÔøΩiÔøΩ\rHgÔø',NULL,NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(20,6,'5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03','.@ÔøΩÔøΩ<K+ÔøΩÔ','text/plain',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(21,27,'eccf61f9770be39afd1efe2c8ec5bdbf2ddc3d3cf30a688bf6a18bf4dac45048','ÔøΩÔøΩÔøΩÔøΩÔøΩÔ','text/html',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(22,2837,'6a10813ed0f5a12fb60a530aed347f74b32c0de65da5f8b4f14cd459469bfb30','ÔøΩ.ÔøΩÔøΩMÔøΩ',NULL,NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(23,13,'31b75c53af215582d8b94e90730e58dd711f17b2c6c9128836ba98e8620892c8','ÔøΩÔøΩÔøΩÔøΩ8GÔ','text/plain',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(24,34,'889eddcafac71f421c65339c0c38bec66940ffdd76adedce2472a4edf704398d','ŸÇÔøΩÔøΩÔøΩOWÔø','text/html',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(25,1949,'46866e65955fdb44934bda5241facc2e5351d85bc58d5fe4363bacd99dfbed9b','ÔøΩÔøΩÔøΩ8ÔøΩD',NULL,NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(26,27,'a87dd39d644c9330f2f60ea9458b35c503352a3d6a9be0339f5b3b44d8239d88',' ÜÔøΩ\"5VO.ÔøΩÔøΩ','text/plain',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(27,63,'d560107b9f59d09cabcbc2633bbf986545e2bd41f3517655d7b8bf3c7dea7786','ÔøΩ`ÔøΩÔøΩÔøΩÔøΩ','text/html',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(28,2224,'f9f27dc47aa42dcd7dc0140be6723e58942ae5f4b5a4947ff43d8c427991917c','‘ïÔøΩqÔøΩL_ÔøΩQ',NULL,NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(29,993,'3d747459c9884417e66ceb56b4f1811b15cfb3fc8efcf1bfb4ac88e3859fa4f0','Õ∂xdRBÿüÔøΩÔøΩ\\','text/plain',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(30,5575,'e956c365e2a7b8481070dde8bdd3d741d799f32f2c208a44a8b6aac9c377419a','ÔøΩYeÔøΩÔøΩJlÔø','text/html',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(31,6321,'2991102bf5c783ea6f018731a8939ee97a4d7562a76e8188775447e3c6e0876f','+ÔøΩÔøΩÔøΩÔøΩÔøΩ','image/png',NULL,'google.png',1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(32,565,'ff3f6b9d30f972e18d28a27d9c19aee77c5f704de8cf490a502c1389c2caf93a','ÔøΩg3ÔøΩT!HÔøΩ9','image/png',NULL,'profilephoto.png',1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(33,891,'21ddd725936b604c5b970431f6f44c3887797938c8ba98525bb2098c128aed81','qÔøΩÂ∫âÔøΩLÔøΩÔø',NULL,NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(34,31,'7747fbe457d3e6d5ead68b4d6f39d17cc2b33e24f9fa78ee40dfe8accbad8ae0','YÔøΩÔøΩÔøΩÔøΩÔøΩ',NULL,'text/text',NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(35,61,'8c9624e032689b58d2dfa87635f7a2ae2d0b4faa06312065eeacde739c1f2252','ÔøΩÔøΩÔøΩÔøΩÔøΩ^','text/html',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(36,852,'553b8ce2185f5d66380cf0209f81cb2fa6a3a0e1f59845d8530ed08b38e96a0e','\0ÔøΩÔøΩa!@“ãÔøΩ',NULL,NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(37,31,'7747fbe457d3e6d5ead68b4d6f39d17cc2b33e24f9fa78ee40dfe8accbad8ae0','w\nÔøΩDI#ÔøΩÔø',NULL,'text/text',NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(38,61,'8c9624e032689b58d2dfa87635f7a2ae2d0b4faa06312065eeacde739c1f2252','ÔøΩ@ÔøΩÔøΩ1NÔøΩ','text/html',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(39,853,'5f015f0eab6e3adcf8320221b6b0686b73f05a2a3cae54e7367f1d42ba44c734','Q0+GX0BÔøΩÔøΩEÔø',NULL,NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(40,31,'7747fbe457d3e6d5ead68b4d6f39d17cc2b33e24f9fa78ee40dfe8accbad8ae0','ÔøΩ3ÔøΩrÔøΩALÔø',NULL,'text/text',NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(41,61,'8c9624e032689b58d2dfa87635f7a2ae2d0b4faa06312065eeacde739c1f2252','ÔøΩÔøΩÔøΩP¬öKÔøΩ','text/html',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(42,858,'0b940bea3d7f6e2523605b3e5e91f3d93aa38d780d6ba49f6fd3664ee3b0eaad','ÔøΩHl@ÔøΩÔøΩDlÔø',NULL,NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(43,31,'7747fbe457d3e6d5ead68b4d6f39d17cc2b33e24f9fa78ee40dfe8accbad8ae0','5?)ÔøΩÔøΩLpÔøΩx',NULL,'text/text',NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(44,61,'8c9624e032689b58d2dfa87635f7a2ae2d0b4faa06312065eeacde739c1f2252','ÔøΩÔøΩÔøΩÔøΩ-H','text/html',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(45,895,'42cefe658856c48397713f475e04af3059fa8c43ee5cc67b7c25ff822f6fdd1c','vÔøΩdÔøΩzÔøΩEÔø',NULL,NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(46,31,'7747fbe457d3e6d5ead68b4d6f39d17cc2b33e24f9fa78ee40dfe8accbad8ae0','ÔøΩÔøΩ0ÔøΩÔøΩ\'CX',NULL,'text/text',NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(47,61,'8c9624e032689b58d2dfa87635f7a2ae2d0b4faa06312065eeacde739c1f2252','ÔøΩÔøΩÔøΩÔøΩc:@Ô','text/html',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(48,3092,'3a50e724e41242746339a2ad4accd821dca20a73844848c54556d5fc13e58a31','LÔøΩÔøΩ8ÔøΩLTÔø',NULL,NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(49,2722,'d30c644879e3b7b618dd03d593e67a9b6ff80615e4aea01b06b992dbed47008a','^ÔøΩEÔøΩR8DÔøΩÔø','text/plain',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(50,6605,'37a1732d9a602ad020d4bf3c878571d8c19eb968ca61a382a4d2d3fb5e8ef896','ÔøΩÔøΩC÷âÔøΩHÔøΩ','text/html',NULL,NULL,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL);
/*!40000 ALTER TABLE `block` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `calendar`
--

DROP TABLE IF EXISTS `calendar`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `calendar` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `public_id` binary(16) NOT NULL,
  `account_id` int(11) NOT NULL,
  `name` varchar(128) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `notes` text,
  `uid` varchar(767) CHARACTER SET ascii NOT NULL,
  `read_only` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`account_id`,`name`),
  CONSTRAINT `calendar_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `calendar`
--

LOCK TABLES `calendar` WRITE;
/*!40000 ALTER TABLE `calendar` DISABLE KEYS */;
INSERT INTO `calendar` VALUES (1,'œ5ˆê¨F\0ªÌ´Åûˆ√¿',1,NULL,NULL,NULL,NULL,NULL,'167wjlgf89za2cdhy17p9bsu8',0);
/*!40000 ALTER TABLE `calendar` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `contact`
--

DROP TABLE IF EXISTS `contact`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `contact` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `public_id` binary(16) NOT NULL,
  `account_id` int(11) NOT NULL,
  `uid` varchar(64) NOT NULL,
  `provider_name` varchar(64) DEFAULT NULL,
  `source` enum('local','remote') DEFAULT NULL,
  `name` text,
  `raw_data` text,
  `score` int(11) DEFAULT NULL,
  `updated_at` datetime NOT NULL,
  `created_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `_canonicalized_address` varchar(191) DEFAULT NULL,
  `_raw_address` varchar(191) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uid` (`uid`,`source`,`account_id`,`provider_name`),
  KEY `account_id` (`account_id`),
  KEY `ix_contact_public_id` (`public_id`),
  KEY `ix_contact_created_at` (`created_at`),
  KEY `ix_contact_deleted_at` (`deleted_at`),
  KEY `ix_contact_updated_at` (`updated_at`),
  KEY `ix_contact__canonicalized_address` (`_canonicalized_address`),
  KEY `ix_contact__raw_address` (`_raw_address`),
  CONSTRAINT `contact_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `contact`
--

LOCK TABLES `contact` WRITE;
/*!40000 ALTER TABLE `contact` DISABLE KEYS */;
INSERT INTO `contact` VALUES (1,'ÔøΩZÔøΩzoÔøΩL?Ôø',1,'ac99aa06-5604-4234-9ccc-dfb5f41973d1','inbox','local','',NULL,24,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL,'inboxapptest@gmail.com','inboxapptest@gmail.com'),(2,'ÔøΩ6\",NA@ÔøΩÔøΩÔ',1,'523f7769-c26e-4728-921d-ffd43e5bb1b4','inbox','local','Ben Bitdiddle',NULL,10,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL,'benbitdiddle1861@gmail.com','benbitdiddle1861@gmail.com'),(3,'ÔøΩ4ÔøΩ-;KÔøΩÔø',1,'0ff75111-5a72-46a4-a0d0-d1d189422117','inbox','local','Paul Tiseo',NULL,10,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL,'paulxtiseo@gmail.com','paulxtiseo@gmail.com'),(4,'ÔøΩÔøΩÔøΩ&mN@ÔøΩ',1,'6840fd76-34e3-4b1a-b0a3-6b797bbf92d7','inbox','local','golang-nuts',NULL,9,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL,'golang-nuts@googlegroups.com','golang-nuts@googlegroups.com'),(5,'ÔøΩ`<]JÔøΩÔøΩ',1,'31d28d81-67df-479b-ae79-6f19589a88dd','inbox','local','Gmail Team',NULL,9,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL,'mail-noreply@google.com','mail-noreply@google.com'),(6,'\\ÔøΩ#eÔøΩHxÔøΩÔ',1,'c0849c30-e29d-4404-b931-ddf9c3d06201','inbox','local','Christine Spang',NULL,9,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL,'christine@spang.cc','christine@spang.cc'),(7,'ÔøΩÔøΩ>J0ÔøΩ',1,'94d616ac-3963-442a-9d05-b88d43a94758','inbox','local','',NULL,9,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL,'no-reply@accounts.google.com','no-reply@accounts.google.com'),(8,'amXÔøΩT@¬ò6ÔøΩ>',1,'47c6565a-2c8e-49a5-a32c-9a7aff921248','inbox','local','kavya joshi',NULL,9,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL,'kavya719@gmail.com','kavya719@gmail.com');
/*!40000 ALTER TABLE `contact` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `draftthread`
--

DROP TABLE IF EXISTS `draftthread`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `draftthread` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `master_public_id` binary(16) NOT NULL,
  `thread_id` int(11) DEFAULT NULL,
  `message_id` int(11) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT '2014-05-22 18:48:31',
  `updated_at` datetime NOT NULL DEFAULT '2014-05-22 18:48:31',
  `deleted_at` datetime DEFAULT NULL,
  `public_id` binary(16) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `thread_id` (`thread_id`),
  KEY `message_id` (`message_id`),
  KEY `ix_draftthread_public_id` (`public_id`),
  CONSTRAINT `draftthread_ibfk_1` FOREIGN KEY (`thread_id`) REFERENCES `thread` (`id`) ON DELETE CASCADE,
  CONSTRAINT `draftthread_ibfk_2` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `draftthread`
--

LOCK TABLES `draftthread` WRITE;
/*!40000 ALTER TABLE `draftthread` DISABLE KEYS */;
INSERT INTO `draftthread` VALUES (1,'(ÔøΩ5ÔøΩÔøΩr@qÔø',16,16,'2014-06-28 00:56:57','2014-06-28 00:56:57',NULL,'tÔøΩ5ÔøΩMMÔøΩÔø');
/*!40000 ALTER TABLE `draftthread` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `easaccount`
--

DROP TABLE IF EXISTS `easaccount`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `easaccount` (
  `id` int(11) NOT NULL,
  `_eas_device_id` varchar(32) DEFAULT NULL,
  `_eas_device_type` varchar(32) DEFAULT NULL,
  `eas_server` varchar(512) DEFAULT NULL,
  `eas_policy_key` varchar(64) DEFAULT NULL,
  `eas_account_sync_key` varchar(64) NOT NULL DEFAULT '0',
  `eas_state` enum('sync','sync keyinvalid','finish') DEFAULT 'sync',
  `password` varchar(256) DEFAULT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `easaccount_ibfk_1` FOREIGN KEY (`id`) REFERENCES `account` (`id`) ON DELETE CASCADE
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
-- Table structure for table `easfoldersync`
--

DROP TABLE IF EXISTS `easfoldersync`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `easfoldersync` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `account_id` int(11) NOT NULL,
  `folder_name` varchar(191) NOT NULL,
  `state` enum('initial','initial uidinvalid','poll','poll uidinvalid','finish') NOT NULL,
  `eas_folder_sync_key` varchar(64) NOT NULL,
  `eas_folder_id` varchar(64) DEFAULT NULL,
  `eas_folder_type` varchar(64) DEFAULT NULL,
  `eas_parent_id` varchar(64) DEFAULT NULL,
  `remote_uid_count` int(11) DEFAULT NULL,
  `uid_checked_date` datetime DEFAULT NULL,
  `_sync_status` text,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_account_id_eas_folder_id` (`account_id`,`eas_folder_id`),
  CONSTRAINT `easfoldersync_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `easaccount` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `easfoldersync`
--

LOCK TABLES `easfoldersync` WRITE;
/*!40000 ALTER TABLE `easfoldersync` DISABLE KEYS */;
/*!40000 ALTER TABLE `easfoldersync` ENABLE KEYS */;
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
  `folder_id` int(11) NOT NULL,
  `state` enum('initial','initial keyinvalid','poll','poll keyinvalid','finish') NOT NULL DEFAULT 'initial',
  `eas_folder_sync_key` varchar(64) NOT NULL,
  `eas_folder_id` varchar(64) DEFAULT NULL,
  `eas_folder_type` varchar(64) DEFAULT NULL,
  `eas_parent_id` varchar(64) DEFAULT NULL,
  `_metrics` text,
  PRIMARY KEY (`id`),
  UNIQUE KEY `account_id` (`account_id`,`folder_id`),
  UNIQUE KEY `account_id_2` (`account_id`,`eas_folder_id`),
  KEY `folder_id` (`folder_id`),
  KEY `ix_easfoldersyncstatus_created_at` (`created_at`),
  KEY `ix_easfoldersyncstatus_deleted_at` (`deleted_at`),
  KEY `ix_easfoldersyncstatus_updated_at` (`updated_at`),
  CONSTRAINT `easfoldersyncstatus_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `easaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `easfoldersyncstatus_ibfk_2` FOREIGN KEY (`folder_id`) REFERENCES `folder` (`id`)
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
  `message_id` int(11) DEFAULT NULL,
  `fld_uid` int(11) NOT NULL,
  `msg_uid` int(11) DEFAULT NULL,
  `folder_id` int(11) NOT NULL,
  `is_draft` tinyint(1) NOT NULL,
  `is_flagged` tinyint(1) NOT NULL,
  `is_seen` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `folder_id` (`folder_id`,`msg_uid`,`easaccount_id`),
  KEY `message_id` (`message_id`),
  KEY `ix_easuid_deleted_at` (`deleted_at`),
  KEY `ix_easuid_msg_uid` (`msg_uid`),
  KEY `easuid_easaccount_id_folder_id` (`easaccount_id`,`folder_id`),
  KEY `ix_easuid_created_at` (`created_at`),
  KEY `ix_easuid_updated_at` (`updated_at`),
  CONSTRAINT `easuid_ibfk_1` FOREIGN KEY (`easaccount_id`) REFERENCES `easaccount` (`id`) ON DELETE CASCADE,
  CONSTRAINT `easuid_ibfk_2` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`),
  CONSTRAINT `easuid_ibfk_3` FOREIGN KEY (`folder_id`) REFERENCES `folder` (`id`) ON DELETE CASCADE
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
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `uid` varchar(767) CHARACTER SET ascii DEFAULT NULL,
  `provider_name` varchar(64) NOT NULL,
  `public_id` binary(16) NOT NULL,
  `raw_data` text NOT NULL,
  `account_id` int(11) NOT NULL,
  `subject` varchar(1024) DEFAULT NULL,
  `body` text,
  `location` varchar(255) DEFAULT NULL,
  `busy` tinyint(1) NOT NULL,
  `reminders` varchar(255) DEFAULT NULL,
  `recurrence` varchar(255) DEFAULT NULL,
  `start` datetime DEFAULT NULL,
  `end` datetime DEFAULT NULL,
  `all_day` tinyint(1) NOT NULL,
  `source` enum('remote','local') NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `calendar_id` int(11) NOT NULL,
  `owner` varchar(255) DEFAULT NULL,
  `is_owner` tinyint(1) NOT NULL,
  `read_only` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uid`,`source`,`account_id`,`provider_name`),
  KEY `account_id` (`account_id`),
  KEY `event_ibfk_2` (`calendar_id`),
  CONSTRAINT `event_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `event_ibfk_2` FOREIGN KEY (`calendar_id`) REFERENCES `calendar` (`id`)
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
-- Table structure for table `eventparticipant`
--

DROP TABLE IF EXISTS `eventparticipant`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `eventparticipant` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `public_id` binary(16) NOT NULL,
  `event_id` int(11) NOT NULL,
  `name` varchar(255) DEFAULT NULL,
  `_raw_address` varchar(191) DEFAULT NULL,
  `_canonicalized_address` varchar(191) DEFAULT NULL,
  `status` enum('yes','no','maybe','noreply') NOT NULL,
  `notes` text,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `guests` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uid` (`_raw_address`,`event_id`),
  KEY `event_id` (`event_id`),
  CONSTRAINT `eventparticipant_ibfk_1` FOREIGN KEY (`event_id`) REFERENCES `event` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `eventparticipant`
--

LOCK TABLES `eventparticipant` WRITE;
/*!40000 ALTER TABLE `eventparticipant` DISABLE KEYS */;
/*!40000 ALTER TABLE `eventparticipant` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `folder`
--

DROP TABLE IF EXISTS `folder`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `folder` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `account_id` int(11) NOT NULL,
  `name` varchar(191) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `canonical_name` varchar(191) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `account_id` (`account_id`,`name`,`canonical_name`),
  KEY `ix_folder_created_at` (`created_at`),
  KEY `ix_folder_deleted_at` (`deleted_at`),
  KEY `ix_folder_updated_at` (`updated_at`),
  CONSTRAINT `folder_fk1` FOREIGN KEY (`account_id`) REFERENCES `account` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `folder`
--

LOCK TABLES `folder` WRITE;
/*!40000 ALTER TABLE `folder` DISABLE KEYS */;
INSERT INTO `folder` VALUES (1,1,'[Gmail]/Important','2014-05-13 02:19:12','2014-05-13 02:19:12',NULL,'important'),(2,1,'Inbox','2014-05-13 02:19:12','2014-05-13 02:19:12',NULL,'inbox'),(3,1,'[Gmail]/All Mail','2014-05-13 02:19:12','2014-05-13 02:19:12',NULL,'all'),(4,1,'[Gmail]/Sent Mail','2014-05-13 02:19:12','2014-05-13 02:19:12',NULL,'sent'),(5,1,'[Gmail]/Drafts','2014-05-13 02:19:12','2014-05-13 02:19:12',NULL,'drafts');
/*!40000 ALTER TABLE `folder` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `folderitem`
--

DROP TABLE IF EXISTS `folderitem`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `folderitem` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `thread_id` int(11) NOT NULL,
  `folder_id` int(11) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `thread_id` (`thread_id`),
  KEY `fk_folder_id` (`folder_id`),
  KEY `ix_folderitem_created_at` (`created_at`),
  KEY `ix_folderitem_deleted_at` (`deleted_at`),
  KEY `ix_folderitem_updated_at` (`updated_at`),
  CONSTRAINT `fk_folder_id` FOREIGN KEY (`folder_id`) REFERENCES `folder` (`id`) ON DELETE CASCADE,
  CONSTRAINT `folderitem_ibfk_1` FOREIGN KEY (`thread_id`) REFERENCES `thread` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=37 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `folderitem`
--

LOCK TABLES `folderitem` WRITE;
/*!40000 ALTER TABLE `folderitem` DISABLE KEYS */;
INSERT INTO `folderitem` VALUES (1,1,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(2,1,2,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(3,1,3,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(4,2,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(5,2,2,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(6,2,3,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(7,3,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(8,3,2,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(9,3,3,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(10,4,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(11,4,2,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(12,4,3,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(13,5,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(14,5,2,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(15,5,3,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(16,6,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(17,6,2,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(18,6,3,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(19,7,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(20,7,2,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(21,7,3,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(22,8,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(23,8,2,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(24,8,3,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(25,9,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(26,9,2,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(27,9,3,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(28,10,2,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(29,10,3,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(30,11,3,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(31,12,3,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(32,13,3,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(33,14,3,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(34,15,3,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(35,16,1,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL),(36,16,3,'2014-05-13 02:19:12','2014-05-13 02:19:12',NULL);
/*!40000 ALTER TABLE `folderitem` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `foldersync`
--

DROP TABLE IF EXISTS `foldersync`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `foldersync` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `account_id` int(11) NOT NULL,
  `folder_name` varchar(191) NOT NULL,
  `state` enum('initial','initial uidinvalid','poll','poll uidinvalid','finish') NOT NULL DEFAULT 'initial',
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `_sync_status` text,
  PRIMARY KEY (`id`),
  UNIQUE KEY `account_id` (`account_id`,`folder_name`),
  KEY `ix_foldersync_created_at` (`created_at`),
  KEY `ix_foldersync_deleted_at` (`deleted_at`),
  KEY `ix_foldersync_updated_at` (`updated_at`),
  CONSTRAINT `foldersync_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `imapaccount` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `foldersync`
--

LOCK TABLES `foldersync` WRITE;
/*!40000 ALTER TABLE `foldersync` DISABLE KEYS */;
INSERT INTO `foldersync` VALUES (1,1,'INBOX','poll','2014-05-13 02:19:12','2014-05-13 02:19:12',NULL,NULL),(2,1,'[Gmail]/All Mail','poll','2014-05-13 02:19:12','2014-05-13 02:19:12',NULL,NULL);
/*!40000 ALTER TABLE `foldersync` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `genericaccount`
--

DROP TABLE IF EXISTS `genericaccount`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `genericaccount` (
  `id` int(11) NOT NULL,
  `password_id` int(11) DEFAULT NULL,
  `provider` varchar(64) NOT NULL,
  `supports_condstore` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `genericaccount_ibfk_1` FOREIGN KEY (`id`) REFERENCES `imapaccount` (`id`) ON DELETE CASCADE
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
  `scope` varchar(512) DEFAULT NULL,
  `access_type` varchar(64) DEFAULT NULL,
  `family_name` varchar(256) DEFAULT NULL,
  `given_name` varchar(256) DEFAULT NULL,
  `name` varchar(256) DEFAULT NULL,
  `gender` varchar(16) DEFAULT NULL,
  `g_id` varchar(32) DEFAULT NULL,
  `g_id_token` varchar(1024) DEFAULT NULL,
  `g_user_id` varchar(32) DEFAULT NULL,
  `link` varchar(256) DEFAULT NULL,
  `locale` varchar(8) DEFAULT NULL,
  `picture` varchar(1024) DEFAULT NULL,
  `home_domain` varchar(256) DEFAULT NULL,
  `refresh_token_id` int(11) DEFAULT NULL,
  `client_id` varchar(256) DEFAULT NULL,
  `client_secret` varchar(256) DEFAULT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `gmailaccount_ibfk_1` FOREIGN KEY (`id`) REFERENCES `imapaccount` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `gmailaccount`
--

LOCK TABLES `gmailaccount` WRITE;
/*!40000 ALTER TABLE `gmailaccount` DISABLE KEYS */;
INSERT INTO `gmailaccount` VALUES (1,'https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile https://mail.google.com/ https://www.google.com/m8/feeds https://www.googleapis.com/auth/calendar','offline','App','Inbox',NULL,'other','115086935419017912828','eyJhbGciOiJSUzI1NiIsImtpZCI6IjU3YjcwYzNhMTM4MjA5OTliZjhlNmIxYTBkMDdkYjRlNDVhMmE3NzMifQ.eyJpc3MiOiJhY2NvdW50cy5nb29nbGUuY29tIiwiaWQiOiIxMTUwODY5MzU0MTkwMTc5MTI4MjgiLCJzdWIiOiIxMTUwODY5MzU0MTkwMTc5MTI4MjgiLCJhenAiOiI5ODY2NTk3NzY1MTYtZmc3OW1xYmtia3RmNWt1MTBjMjE1dmRpajkxOHJhMGEuYXBwcy5nb29nbGV1c2VyY29udGVudC5jb20iLCJlbWFpbCI6ImluYm94YXBwdGVzdEBnbWFpbC5jb20iLCJhdF9oYXNoIjoiS090Q0hvQ01mSjNQcmdGSVIwNDFtQSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJhdWQiOiI5ODY2NTk3NzY1MTYtZmc3OW1xYmtia3RmNWt1MTBjMjE1dmRpajkxOHJhMGEuYXBwcy5nb29nbGV1c2VyY29udGVudC5jb20iLCJ0b2tlbl9oYXNoIjoiS090Q0hvQ01mSjNQcmdGSVIwNDFtQSIsInZlcmlmaWVkX2VtYWlsIjp0cnVlLCJjaWQiOiI5ODY2NTk3NzY1MTYtZmc3OW1xYmtia3RmNWt1MTBjMjE1dmRpajkxOHJhMGEuYXBwcy5nb29nbGV1c2VyY29udGVudC5jb20iLCJpYXQiOjEzOTkwNzk0MDIsImV4cCI6MTM5OTA4MzMwMn0.CFnCmsz3XCK196CF6PQ19z9IUxEeffZ_eu3JVdJE1rDHc1i5h44l1ioNouJinyJhqV4QQmaXDGJ3oggogfF0TGuUbRwcOWs0_oR01ZxuplY0U7s_g96LcZt667L-ZPFZosPM3APvGof2tvDQViyFd0V6rGu3ok49HqatZ8PT5eo','115086935419017912828',NULL,'en',NULL,NULL,1,NULL,NULL);
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
  PRIMARY KEY (`id`),
  CONSTRAINT `imapaccount_ibfk_1` FOREIGN KEY (`id`) REFERENCES `account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `imapaccount`
--

LOCK TABLES `imapaccount` WRITE;
/*!40000 ALTER TABLE `imapaccount` DISABLE KEYS */;
INSERT INTO `imapaccount` VALUES (1);
/*!40000 ALTER TABLE `imapaccount` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `imapfolderinfo`
--

DROP TABLE IF EXISTS `imapfolderinfo`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `imapfolderinfo` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `account_id` int(11) NOT NULL,
  `uidvalidity` bigint(20) NOT NULL,
  `highestmodseq` bigint(20) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `folder_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `imapaccount_id` (`account_id`,`folder_id`),
  KEY `ix_uidvalidity_created_at` (`created_at`),
  KEY `ix_uidvalidity_deleted_at` (`deleted_at`),
  KEY `ix_uidvalidity_updated_at` (`updated_at`),
  KEY `imapfolderinfo_ibfk_2` (`folder_id`),
  CONSTRAINT `imapfolderinfo_ibfk_2` FOREIGN KEY (`folder_id`) REFERENCES `folder` (`id`),
  CONSTRAINT `imapfolderinfo_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `imapaccount` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `imapfolderinfo`
--

LOCK TABLES `imapfolderinfo` WRITE;
/*!40000 ALTER TABLE `imapfolderinfo` DISABLE KEYS */;
INSERT INTO `imapfolderinfo` VALUES (1,1,1,106957,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,2),(2,1,11,106957,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,3);
/*!40000 ALTER TABLE `imapfolderinfo` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `imapfoldersyncstatus`
--

DROP TABLE IF EXISTS `imapfoldersyncstatus`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `imapfoldersyncstatus` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `account_id` int(11) NOT NULL,
  `state` enum('initial','initial uidinvalid','poll','poll uidinvalid','finish') NOT NULL DEFAULT 'initial',
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `_metrics` text,
  `folder_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `account_id` (`account_id`,`folder_id`),
  KEY `ix_foldersync_created_at` (`created_at`),
  KEY `ix_foldersync_deleted_at` (`deleted_at`),
  KEY `ix_foldersync_updated_at` (`updated_at`),
  KEY `imapfoldersyncstatus_ibfk_2` (`folder_id`),
  CONSTRAINT `imapfoldersyncstatus_ibfk_2` FOREIGN KEY (`folder_id`) REFERENCES `folder` (`id`),
  CONSTRAINT `imapfoldersyncstatus_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `imapaccount` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `imapfoldersyncstatus`
--

LOCK TABLES `imapfoldersyncstatus` WRITE;
/*!40000 ALTER TABLE `imapfoldersyncstatus` DISABLE KEYS */;
INSERT INTO `imapfoldersyncstatus` VALUES (1,1,'poll','2014-05-13 02:19:12','2014-05-13 02:19:12',NULL,NULL,2),(2,1,'poll','2014-05-13 02:19:12','2014-05-13 02:19:12',NULL,NULL,3);
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
INSERT INTO `imapthread` VALUES (3,1443911956831022215),(10,1449471921372979402),(4,1463159441433026019),(1,1464327557735981576),(5,1464328115838585338),(7,1464328502421499234),(9,1464329212533881603),(8,1464329835043990839),(6,1464330773292835572),(16,1466255156975764289),(15,1466761259745473801),(14,1466761634398434761),(13,1466854894292093968),(12,1466855488650356657),(11,1466856002099058157),(2,1467038319150540079);
/*!40000 ALTER TABLE `imapthread` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `imapuid`
--

DROP TABLE IF EXISTS `imapuid`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `imapuid` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `account_id` int(11) NOT NULL,
  `message_id` int(11) NOT NULL,
  `msg_uid` bigint(20) NOT NULL,
  `is_draft` tinyint(1) NOT NULL DEFAULT '0',
  `is_seen` tinyint(1) NOT NULL DEFAULT '0',
  `is_flagged` tinyint(1) NOT NULL DEFAULT '0',
  `is_recent` tinyint(1) NOT NULL DEFAULT '0',
  `is_answered` tinyint(1) NOT NULL DEFAULT '0',
  `extra_flags` varchar(255) NOT NULL,
  `folder_id` int(11) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_imapuid_folder_id_msg_uid_imapaccount_id` (`folder_id`,`msg_uid`,`account_id`),
  KEY `message_id` (`message_id`),
  KEY `imapaccount_id_folder_id` (`account_id`,`folder_id`),
  KEY `ix_imapuid_created_at` (`created_at`),
  KEY `ix_imapuid_deleted_at` (`deleted_at`),
  KEY `ix_imapuid_updated_at` (`updated_at`),
  CONSTRAINT `imapuid_ibfk_2` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`) ON DELETE CASCADE,
  CONSTRAINT `imapuid_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `imapaccount` (`id`),
  CONSTRAINT `imapuid_ibfk_3` FOREIGN KEY (`folder_id`) REFERENCES `folder` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=27 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `imapuid`
--

LOCK TABLES `imapuid` WRITE;
/*!40000 ALTER TABLE `imapuid` DISABLE KEYS */;
INSERT INTO `imapuid` VALUES (2,1,1,380,0,0,0,0,0,'[]',2,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(4,1,2,943,0,1,0,0,0,'[]',2,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(6,1,3,934,0,1,0,0,0,'[]',2,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(8,1,4,555,0,0,0,0,0,'[]',2,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(10,1,5,554,0,0,0,0,0,'[]',2,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(12,1,6,406,0,1,0,0,0,'[]',2,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(14,1,7,385,0,0,0,0,0,'[]',2,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(16,1,8,378,0,1,0,0,0,'[]',2,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(18,1,9,377,0,0,0,0,0,'[]',2,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(20,1,10,375,0,0,0,0,0,'[]',2,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(21,1,11,341,0,0,0,0,0,'[]',3,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(22,1,12,339,0,0,0,0,0,'[]',3,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(23,1,13,338,0,0,0,0,0,'[]',3,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(24,1,14,320,0,0,0,0,0,'[]',3,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(25,1,15,316,0,0,0,0,0,'[]',3,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(26,1,16,184,0,1,0,0,0,'[]',3,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL);
/*!40000 ALTER TABLE `imapuid` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `lens`
--

DROP TABLE IF EXISTS `lens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `lens` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `public_id` binary(16) NOT NULL,
  `namespace_id` int(11) NOT NULL,
  `subject` varchar(255) DEFAULT NULL,
  `thread_public_id` binary(16) DEFAULT NULL,
  `started_before` datetime DEFAULT NULL,
  `started_after` datetime DEFAULT NULL,
  `last_message_before` datetime DEFAULT NULL,
  `last_message_after` datetime DEFAULT NULL,
  `any_email` varchar(255) DEFAULT NULL,
  `to_addr` varchar(255) DEFAULT NULL,
  `from_addr` varchar(255) DEFAULT NULL,
  `cc_addr` varchar(255) DEFAULT NULL,
  `bcc_addr` varchar(255) DEFAULT NULL,
  `filename` varchar(255) DEFAULT NULL,
  `tag` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_lens_namespace_id` (`namespace_id`),
  KEY `ix_lens_public_id` (`public_id`),
  KEY `ix_lens_created_at` (`created_at`),
  KEY `ix_lens_deleted_at` (`deleted_at`),
  KEY `ix_lens_updated_at` (`updated_at`),
  CONSTRAINT `lens_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `lens`
--

LOCK TABLES `lens` WRITE;
/*!40000 ALTER TABLE `lens` DISABLE KEYS */;
/*!40000 ALTER TABLE `lens` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `liveaccount`
--

DROP TABLE IF EXISTS `liveaccount`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `liveaccount` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `account_id` int(11) NOT NULL,
  `state` int(11) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `liveaccount`
--

LOCK TABLES `liveaccount` WRITE;
/*!40000 ALTER TABLE `liveaccount` DISABLE KEYS */;
INSERT INTO `liveaccount` VALUES (1,'2014-07-16 01:52:31','2014-07-16 01:52:31',NULL,1,0);
/*!40000 ALTER TABLE `liveaccount` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `message`
--

DROP TABLE IF EXISTS `message`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `message` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `public_id` binary(16) NOT NULL,
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
  `sanitized_body` longtext NOT NULL,
  `snippet` varchar(191) NOT NULL,
  `decode_error` tinyint(1) NOT NULL DEFAULT '0',
  `g_msgid` bigint(20) DEFAULT NULL,
  `g_thrid` bigint(20) DEFAULT NULL,
  `inbox_uid` varchar(64) DEFAULT NULL,
  `references` text,
  `type` varchar(16) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `is_read` tinyint(1) NOT NULL DEFAULT '0',
  `is_created` tinyint(1) NOT NULL DEFAULT '0',
  `is_sent` tinyint(1) NOT NULL DEFAULT '0',
  `state` enum('draft','sending','sending failed','sent') DEFAULT NULL,
  `is_reply` tinyint(1) DEFAULT NULL,
  `resolved_message_id` int(11) DEFAULT NULL,
  `thread_order` int(11) NOT NULL,
  `version` binary(16) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `thread_id_2` (`thread_id`,`g_msgid`),
  KEY `thread_id` (`thread_id`),
  KEY `ix_message_g_msgid` (`g_msgid`),
  KEY `ix_message_public_id` (`public_id`),
  KEY `ix_message_g_thrid` (`g_thrid`),
  KEY `ix_message_created_at` (`created_at`),
  KEY `ix_message_deleted_at` (`deleted_at`),
  KEY `ix_message_updated_at` (`updated_at`),
  KEY `message_ibfk_2` (`resolved_message_id`),
  CONSTRAINT `message_ibfk_1` FOREIGN KEY (`thread_id`) REFERENCES `thread` (`id`) ON DELETE CASCADE,
  CONSTRAINT `message_ibfk_2` FOREIGN KEY (`resolved_message_id`) REFERENCES `message` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `message`
--

LOCK TABLES `message` WRITE;
/*!40000 ALTER TABLE `message` DISABLE KEYS */;
INSERT INTO `message` VALUES (1,'ÔøΩb\"_MFÔøΩÔøΩÔ',1,'[[\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]]','[]','[]','[[\"\", \"inboxapptest@gmail.com\"]]','[]','[]',NULL,'<CABO4WuP6D+RUW5T_ZbER9T-O--qYDj_JbgD72RGGfrSkJteQ4Q@mail.gmail.com>','asiuhdakhsdf','2014-04-03 02:19:42',2127,'f92545e762b44776e0cb3fdad773f47a563fd5cb72a7fc31c26a2c43cc764343',0,'<html><body><div dir=\"ltr\">iuhasdklfhasdf</div></body></html>','iuhasdklfhasdf',0,1464327557735981576,1464327557735981576,NULL,'[]','message','2014-05-13 02:19:13','2014-08-27 01:13:29',NULL,0,0,0,NULL,NULL,NULL,0,NULL),(2,'zRÔøΩÔøΩDc@7ÔøΩÔ',2,'[[\"\'Rui Ueyama\' via golang-nuts\", \"golang-nuts@googlegroups.com\"]]','[[\"\", \"golang-nuts@googlegroups.com\"]]','[[\"Rui Ueyama\", \"ruiu@google.com\"]]','[[\"Paul Tiseo\", \"paulxtiseo@gmail.com\"]]','[[\"golang-nuts\", \"golang-nuts@googlegroups.com\"]]','[]','\"<1286bda0-97a1-47c4-be2d-93b2640f2435@googlegroups.com>\"','<CAJENXgt5t4yYJdDuV7m2DKwcDEbsY8TohVWmgmMqhnqC3pGwMw@mail.gmail.com>','[go-nuts] Runtime Panic On Method Call','2014-05-03 00:26:05',10447,'e317a191277854cb8b88481268940441a065bad48d02d5a477f0564d4cbe5297',0,'<html><body><div dir=\"ltr\">I\'d think you\'ll get more help if you can reproduce the issue with smaller code and paste it to Go Playground.<div class=\"gmail_extra\"></div></div>\n<p></p>\n\n-- <br/>\nYou received this message because you are subscribed to the Google Groups \"golang-nuts\" group.<br/>\nTo unsubscribe from this group and stop receiving emails from it, send an email to <a href=\"mailto:golang-nuts+unsubscribe@googlegroups.com\">golang-nuts+unsubscribe@googlegroups.com</a>.<br/>\nFor more options, visit <a href=\"https://groups.google.com/d/optout\">https://groups.google.com/d/optout</a>.<br/></body></html>','I\'d think you\'ll get more help if you can reproduce the issue with smaller code and paste it to Go Playground. \n \n\n--  \nYou received this message because you are subscribed to the Google Grou',0,1467038319150540079,1467038319150540079,NULL,'[\"<1286bda0-97a1-47c4-be2d-93b2640f2435@googlegroups.com>\"]','message','2014-05-13 02:19:13','2014-08-27 01:13:29',NULL,1,0,0,NULL,NULL,NULL,0,NULL),(3,'ÔøΩÔøΩ%ÔøΩlBÔø',3,'[[\"Gmail Team\", \"mail-noreply@google.com\"]]','[]','[]','[[\"Inbox App\", \"inboxapptest@gmail.com\"]]','[]','[]',NULL,'<CAOPuB_MAEq7GsOVvWgE+qHR_6vWYXifHhF+hQ1sFyzk_eKPYpQ@mail.gmail.com>','Tips for using Gmail','2013-08-20 18:02:28',15711,'8f62d93f04735652b9f4edc89bc764e5b48fff1bcd0acec67718047c81d76051',0,'<html xmlns=\"http://www.w3.org/1999/xhtml\"><head><meta content=\"text/html;charset=utf-8\" http-equiv=\"content-type\"/><title>Tips for using Gmail</title></head><body link=\"#1155CC\" marginheight=\"0\" marginwidth=\"0\" text=\"#444444\">\n<table bgcolor=\"#f5f5f5\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse: collapse;\" width=\"100%\">\n<tr>\n<td> </td>\n<td height=\"51\" width=\"64\"><img alt=\"\" height=\"51\" src=\"https://ssl.gstatic.com/drive/announcements/images/framework-top-left.png\" style=\"display:block\" width=\"64\"/></td>\n<td background=\"https://ssl.gstatic.com/drive/announcements/images/framework-top-middle.png\" bgcolor=\"#f5f5f5\" height=\"51\" valign=\"bottom\" width=\"673\">\n</td>\n<td height=\"51\" width=\"64\"><img alt=\"\" height=\"51\" src=\"https://ssl.gstatic.com/drive/announcements/images/framework-top-right.png\" style=\"display:block\" width=\"68\"/></td>\n<td> </td>\n</tr>\n<tr>\n<td> </td>\n<td height=\"225\" width=\"64\"><img alt=\"\" height=\"225\" src=\"https://ssl.gstatic.com/drive/announcements/images/framework-middle-1-left.png\" style=\"display:block\" width=\"64\"/></td>\n<td bgcolor=\"#ffffff\" valign=\"top\" width=\"668\">\n<table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse: collapse; \" width=\"100%\">\n<tr>\n<td colspan=\"3\"> </td>\n</tr>\n<tr>\n<td align=\"center\" colspan=\"3\" height=\"50\" valign=\"bottom\"><img alt=\"\" src=\"https://ssl.gstatic.com/drive/announcements/images/logo.gif\" style=\"display:block\"/></td>\n</tr>\n<tr>\n<td colspan=\"3\" height=\"40\"> </td>\n</tr>\n<tr>\n<td> </td>\n<td width=\"450\">\n<b>\n<font color=\"#444444\" face=\"Arial, sans-serif\" size=\"-1\" style=\"line-height: 1.4em\">\n<img alt=\"\" src=\"https://ssl.gstatic.com/accounts/services/mail/msa/gmail_icon_small.png\" style=\"display:block;float:left;margin-top:4px;margin-right:3px;\"/>Hi Inbox\n                    </font>\n</b>\n</td>\n<td> </td>\n</tr>\n<tr>\n<td height=\"40\" valign=\"top\">\n</td></tr>\n<tr>\n<td width=\"111\"> </td>\n<td align=\"left\">\n<table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse: collapse;\" width=\"540\">\n<tr>\n<td valign=\"top\"><font color=\"#444444\" face=\"Arial, sans-serif\" size=\"+2\"><span style=\"font-family:Open Sans, Arial, sans-serif; font-size: 25px\">Tips for using Gmail</span></font></td>\n</tr>\n</table>\n</td>\n<td width=\"111\"> </td>\n</tr>\n<tr>\n<td colspan=\"3\" height=\"10\"> </td>\n</tr>\n</table>\n</td>\n<td height=\"225\" width=\"64\"><img alt=\"\" height=\"225\" src=\"https://ssl.gstatic.com/drive/announcements/images/framework-middle-1-right.png\" style=\"display:block\" width=\"64\"/></td>\n<td> </td>\n</tr>\n<tr>\n<td> </td>\n<td height=\"950\" width=\"64\"><img alt=\"\" height=\"950\" src=\"https://ssl.gstatic.com/drive/announcements/images/framework-middle-2-left.png\" style=\"display:block\" width=\"64\"/></td>\n<td align=\"center\" bgcolor=\"#ffffff\" valign=\"top\" width=\"668\">\n<table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse: collapse;\" width=\"540\">\n<tr>\n<td align=\"left\">\n<img alt=\"\" src=\"https://ssl.gstatic.com/accounts/services/mail/msa/welcome_hangouts.png\" style=\"display:block\"/>\n</td>\n<td width=\"15\"></td>\n<td align=\"left\" valign=\"middle\">\n<table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;\" width=\"400\">\n<tr>\n<td align=\"left\">\n<font color=\"#444444\" face=\"Arial,sans-serif\" size=\"+1\"><span style=\"font-family:Arial, sans-serif; font-size: 20px;\">Chat right from your inbox</span></font>\n</td>\n</tr>\n<tr>\n<td height=\"10\"></td>\n</tr>\n<tr>\n<td align=\"left\" valign=\"top\">\n<font color=\"#444444\" face=\"Arial,sans-serif\" size=\"-1\" style=\"line-height:1.4em\">Chat with contacts and start video chats with up to 10 people in <a href=\"http://www.google.com/+/learnmore/hangouts/?hl=en\" style=\"text-decoration:none;\">Google+ Hangouts</a>.</font>\n</td>\n</tr>\n</table>\n</td>\n</tr>\n<tr>\n<td colspan=\"3\" height=\"30\"> </td>\n</tr>\n<tr>\n<td align=\"left\">\n<img alt=\"\" src=\"https://ssl.gstatic.com/accounts/services/mail/msa/welcome_contacts.png\" style=\"display:block\"/>\n</td>\n<td width=\"15\"></td>\n<td align=\"left\" valign=\"middle\">\n<table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;\" width=\"400\">\n<tr>\n<td align=\"left\">\n<font color=\"#444444\" face=\"Arial,sans-serif\" size=\"+1\"><span style=\"font-family:Arial, sans-serif; font-size: 20px;\">Bring your email into Gmail</span></font>\n</td>\n</tr>\n<tr>\n<td height=\"10\"></td>\n</tr>\n<tr>\n<td align=\"left\" valign=\"top\">\n<font color=\"#444444\" face=\"Arial,sans-serif\" size=\"-1\" style=\"line-height:1.4em\">You can import your email from other webmail to make the transition to Gmail a bit easier. <a href=\"https://support.google.com/mail/answer/164640?hl=en\" style=\"text-decoration:none;\">Learn how.</a></font>\n</td>\n</tr>\n</table>\n</td>\n</tr>\n<tr>\n<td colspan=\"3\" height=\"30\"> </td>\n</tr>\n<tr>\n<td align=\"left\">\n<img alt=\"\" src=\"https://ssl.gstatic.com/mail/welcome/localized/en/welcome_drive.png\" style=\"display:block\"/>\n</td>\n<td width=\"15\"></td>\n<td align=\"left\" valign=\"middle\">\n<table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;\" width=\"400\">\n<tr>\n<td align=\"left\">\n<font color=\"#444444\" face=\"Arial,sans-serif\" size=\"+1\"><span style=\"font-family:Arial, sans-serif; font-size: 20px;\">Use Google Drive to send large files</span></font>\n</td>\n</tr>\n<tr>\n<td height=\"10\"></td>\n</tr>\n<tr>\n<td align=\"left\" valign=\"top\">\n<font color=\"#444444\" face=\"Arial,sans-serif\" size=\"-1\" style=\"line-height:1.4em\"><a href=\"https://support.google.com/mail/answer/2480713?hl=en\" style=\"text-decoration:none;\">Send huge files in Gmail </a>  (up to 10GB) using <a href=\"https://drive.google.com/?hl=en\" style=\"text-decoration:none;\">Google Drive</a>. Plus files stored in Drive stay up-to-date automatically so everyone has the most recent version and can access them from anywhere.</font>\n</td>\n</tr>\n</table>\n</td>\n</tr>\n<tr>\n<td colspan=\"3\" height=\"30\"> </td>\n</tr>\n<tr>\n<td align=\"left\">\n<img alt=\"\" src=\"https://ssl.gstatic.com/accounts/services/mail/msa/welcome_storage.png\" style=\"display:block\"/>\n</td>\n<td width=\"15\"></td>\n<td align=\"left\" valign=\"middle\">\n<table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;\" width=\"400\">\n<tr>\n<td align=\"left\">\n<font color=\"#444444\" face=\"Arial,sans-serif\" size=\"+1\"><span style=\"font-family:Arial, sans-serif; font-size: 20px;\">Save everything</span></font>\n</td>\n</tr>\n<tr>\n<td height=\"10\"></td>\n</tr>\n<tr>\n<td align=\"left\" valign=\"top\">\n<font color=\"#444444\" face=\"Arial,sans-serif\" size=\"-1\" style=\"line-height:1.4em\">With 10GB of space, you‚Äôll never need to delete an email. Just keep everything and easily find it later.</font>\n</td>\n</tr>\n</table>\n</td>\n</tr>\n<tr>\n<td colspan=\"3\" height=\"30\"> </td>\n</tr>\n<tr>\n<td align=\"left\">\n<img alt=\"\" src=\"https://ssl.gstatic.com/mail/welcome/localized/en/welcome_search.png\" style=\"display:block\"/>\n</td>\n<td width=\"15\"></td>\n<td align=\"left\" valign=\"middle\">\n<table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;\" width=\"400\">\n<tr>\n<td align=\"left\">\n<font color=\"#444444\" face=\"Arial,sans-serif\" size=\"+1\"><span style=\"font-family:Arial, sans-serif; font-size: 20px;\">Find emails fast</span></font>\n</td>\n</tr>\n<tr>\n<td height=\"10\"></td>\n</tr>\n<tr>\n<td align=\"left\" valign=\"top\">\n<font color=\"#444444\" face=\"Arial,sans-serif\" size=\"-1\" style=\"line-height:1.4em\">With the power of Google Search right in your inbox, you can quickly find the important emails you need with suggestions based on emails, past searches and contacts.</font>\n</td>\n</tr>\n</table>\n</td>\n</tr>\n<tr>\n<td colspan=\"3\" height=\"30\"> </td>\n</tr>\n</table>\n<table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse: collapse; \" width=\"500\">\n<tr>\n<td colspan=\"2\" height=\"40\"> </td>\n</tr>\n<tr>\n<td rowspan=\"2\" width=\"68\"><img alt=\"\" src=\"https://ssl.gstatic.com/accounts/services/mail/msa/gmail_icon_large.png\" style=\"display:block\"/></td>\n<td align=\"left\" height=\"20\" valign=\"bottom\"><font color=\"#444444\" face=\"Arial, sans-serif\" size=\"-1\">Happy emailing,</font></td>\n</tr>\n<tr>\n<td align=\"left\" valign=\"top\"><font color=\"#444444\" face=\"Arial, sans-serif\" size=\"+2\"><span style=\"font-family:Open Sans, Arial, sans-serif;\">The Gmail Team</span></font></td>\n</tr>\n<tr>\n<td colspan=\"2\" height=\"60\"> </td>\n</tr>\n</table>\n</td>\n<td height=\"950\" width=\"64\"><img alt=\"\" height=\"950\" src=\"https://ssl.gstatic.com/drive/announcements/images/framework-middle-2-right.png\" style=\"display:block\" width=\"64\"/></td>\n<td> </td>\n</tr>\n<tr>\n<td> </td>\n<td height=\"102\" width=\"64\"><img alt=\"\" height=\"102\" src=\"https://ssl.gstatic.com/drive/announcements/images/framework-bottom-left.png\" style=\"display:block\" width=\"64\"/></td>\n<td background=\"https://ssl.gstatic.com/drive/announcements/images/framework-bottom-middle.png\" height=\"102\" valign=\"top\" width=\"673\">\n<table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse: collapse; \" width=\"100%\">\n<tr>\n<td height=\"12\"></td>\n</tr>\n<tr>\n<td valign=\"bottom\">\n<font color=\"#AAAAAA\" face=\"Arial, sans-serif\" size=\"-2\">\n                  ¬© 2013 Google Inc. 1600 Amphitheatre Parkway, Mountain View, CA 94043\n                </font>\n</td>\n</tr>\n</table>\n</td>\n<td height=\"102\" width=\"64\"><img alt=\"\" height=\"102\" src=\"https://ssl.gstatic.com/drive/announcements/images/framework-bottom-right.png\" style=\"display:block\" width=\"68\"/></td>\n<td> </td>\n</tr>\n</table>\n</body></html>','\n \n \n   \n \n \n \n \n   \n \n \n   \n \n \n \n \n   \n \n \n \n \n \n   \n \n \n   \n \n \n \n Hi Inbox\n                     \n \n \n   \n \n \n \n \n \n   \n \n \n \n Tips for using Gmail \n \n \n \n   \n \n \n   \n \n \n \n \n   \n \n \n   \n ',0,1443911956831022215,1443911956831022215,NULL,'[]','message','2014-05-13 02:19:13','2014-08-27 01:13:29',NULL,1,0,0,NULL,NULL,NULL,0,NULL),(4,'FqRÔøΩÔøΩOÔøΩÔø',4,'[[\"Christine Spang\", \"christine@spang.cc\"]]','[[\"\", \"christine.spang@gmail.com\"]]','[]','[[\"\", \"inboxapptest@gmail.com\"]]','[]','[]',NULL,'<CAFMxqJyA0xft8f67uEcDiTAs8pgfXO26VaipnGHngFB45Vwiog@mail.gmail.com>','trigger poll','2014-03-21 04:53:00',2178,'6b0736bd5f6e9cb4200e1b280ac649229ee78eae1447028a7489b68739506c3a',0,'<html><body><div dir=\"ltr\">hi</div></body></html>','hi',0,1463159441433026019,1463159441433026019,NULL,'[]','message','2014-05-13 02:19:13','2014-08-27 01:13:29',NULL,0,0,0,NULL,NULL,NULL,0,NULL),(5,'@ÔøΩÔøΩhlvKaÔøΩ-',5,'[[\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]]','[]','[]','[[\"\", \"inboxapptest@gmail.com\"]]','[]','[]',NULL,'<CABO4WuM+fcDS9QGXnvOEvm-N8VjF8XxgVLtYLZ0=ENx_0A8u2A@mail.gmail.com>','idle trigger','2014-04-03 02:28:34',3003,'4461bfa07c3638fa6082535ecb1affb98e3a5a855d32543ac6e7f1d66c95c08e',0,'<html><body><div dir=\"ltr\">idle trigger</div></body></html>','idle trigger',0,1464328115838585338,1464328115838585338,NULL,'[]','message','2014-05-13 02:19:13','2014-08-27 01:13:29',NULL,0,0,0,NULL,NULL,NULL,0,NULL),(6,'ÔøΩÔøΩÔøΩ3ÔøΩÔøΩ',6,'[[\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]]','[]','[]','[[\"\", \"inboxapptest@gmail.com\"]]','[]','[]',NULL,'<CABO4WuN+beJ_br_j0uifnXUE+EFAf_bDDBJ0tB-Zkd_2USTc+w@mail.gmail.com>','idle test 123','2014-04-03 03:10:48',2126,'be9b8517433ab5524b7719653d2a057d1f0e4145b4f111e9e4c83dbab6bd6242',0,'<html><body><div dir=\"ltr\">idle test 123</div></body></html>','idle test 123',0,1464330773292835572,1464330773292835572,NULL,'[]','message','2014-05-13 02:19:13','2014-08-27 01:13:29',NULL,1,0,0,NULL,NULL,NULL,0,NULL),(7,':lZTOÔøΩÔøΩÔø',7,'[[\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]]','[]','[]','[[\"\", \"inboxapptest@gmail.com\"]]','[]','[]',NULL,'<CABO4WuNcTC0_37JuNRQugskTCyYM9-HrszhPKfrf+JqOJE8ntA@mail.gmail.com>','another idle test','2014-04-03 02:34:43',2124,'8adff77788264670035888b1cb2afc6edd4a20b50c43f5b11874f2bc84d1c835',0,'<html><body><div dir=\"ltr\">hello</div></body></html>','hello',0,1464328502421499234,1464328502421499234,NULL,'[]','message','2014-05-13 02:19:13','2014-08-27 01:13:29',NULL,0,0,0,NULL,NULL,NULL,0,NULL),(8,'eÔøΩ›Ä]GÔøΩÔøΩ',8,'[[\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]]','[]','[]','[[\"\", \"inboxapptest@gmail.com\"]]','[]','[]',NULL,'<CABO4WuOoG=Haky985B_Lx3J0kBo1o8J+2rH87qdpnyHg1+JVJA@mail.gmail.com>','ohaiulskjndf','2014-04-03 02:55:54',2994,'6e4a76ba1ca34b0b4edd2d164229ad9d4b8a5d53ea53dc214799c93b802f2340',0,'<html><body><div dir=\"ltr\">aoiulhksjndf</div></body></html>','aoiulhksjndf',0,1464329835043990839,1464329835043990839,NULL,'[]','message','2014-05-13 02:19:13','2014-08-27 01:13:29',NULL,1,0,0,NULL,NULL,NULL,0,NULL),(9,'\nkgÔøΩQÔøΩGÔøΩÔø',9,'[[\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]]','[]','[]','[[\"\", \"inboxapptest@gmail.com\"]]','[]','[]',NULL,'<CABO4WuM6jXXOtc7KGU-M4bQKkP3wXxjnrBWFhbznsJDsiauHmA@mail.gmail.com>','guaysdhbjkf','2014-04-03 02:46:00',2165,'e5cc414d931127db23a633eb27b12b1fa7621562ee639487b20c18818cb78437',0,'<html><body><div dir=\"ltr\">a8ogysuidfaysogudhkbjfasdf<div><br/></div></div></body></html>','a8ogysuidfaysogudhkbjfasdf',0,1464329212533881603,1464329212533881603,NULL,'[]','message','2014-05-13 02:19:13','2014-08-27 01:13:29',NULL,0,0,0,NULL,NULL,NULL,0,NULL),(10,'OÔøΩÔøΩÔøΩOÔøΩ',10,'[[\"\", \"no-reply@accounts.google.com\"]]','[]','[]','[[\"\", \"inboxapptest@gmail.com\"]]','[]','[]',NULL,'<MC4rhxPMVYU1ydNeoLDDDA@notifications.google.com>','Google Account recovery phone number changed','2013-10-21 02:55:43',19501,'7836dd4eef7852ea9e9fafae09cc40d18887478d8279d0c2e215c2a7daad3deb',0,'<html lang=\"en\"><body style=\"margin:0; padding: 0;\">\n<table align=\"center\" bgcolor=\"#f1f1f1\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" height=\"100%\" style=\"border-collapse: collapse\" width=\"100%\">\n<tr align=\"center\">\n<td valign=\"top\">\n<table bgcolor=\"#f1f1f1\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" height=\"60\" style=\"border-collapse: collapse\">\n<tr height=\"40\" valign=\"middle\">\n<td width=\"9\"></td>\n<td valign=\"middle\" width=\"217\">\n<img alt=\"Google Accounts\" border=\"0\" height=\"40\" src=\"cid:google\" style=\"display: block;\"/>\n</td>\n<td style=\"font-size: 13px; font-family: arial, sans-serif; color: #777777; text-align: right\" width=\"327\">\n            \n              Inbox App\n            \n          </td>\n<td width=\"10\"></td>\n<td><img src=\"cid:profilephoto\"/></td>\n<td width=\"10\"></td>\n</tr>\n</table>\n<table bgcolor=\"#ffffff\" border=\"1\" bordercolor=\"#e5e5e5\" cellpadding=\"0\" cellspacing=\"0\" style=\"text-align: left\">\n<tr>\n<td height=\"15\" style=\"border-top: none; border-bottom: none; border-left: none; border-right: none;\">\n</td>\n</tr>\n<tr>\n<td style=\"border-top: none; border-bottom: none; border-left: none; border-right: none;\" width=\"15\">\n</td>\n<td style=\"font-size: 83%; border-top: none; border-bottom: none; border-left: none; border-right: none; font-size: 13px; font-family: arial, sans-serif; color: #222222; line-height: 18px\" valign=\"top\" width=\"568\">\n            \n              Hi Inbox,\n              <br/>\n<br/>\n            \n\n\nThe recovery phone number for your Google Account - inboxapptest@gmail.com - was recently changed. If you made this change, you don\'t need to do anything more.\n\n<br/>\n<br/>\n\nIf you didn\'t change your recovery phone, someone may have broken into your account. Visit this link for more information: <a href=\"https://support.google.com/accounts/bin/answer.py?answer=2450236\" style=\"text-decoration: none; color: #4D90FE\">https://support.google.com/accounts/bin/answer.py?answer=2450236</a>.\n\n<br/>\n<br/>\n\nIf you are having problems accessing your account, reset your password by clicking the button below:\n\n<br/>\n<br/>\n<a href=\"https://accounts.google.com/RecoverAccount?fpOnly=1&amp;source=ancrppe&amp;Email=inboxapptest@gmail.com\" style=\"text-align: center; font-size: 11px; font-family: arial, sans-serif; color: white; font-weight: bold; border-color: #3079ed; background-color: #4d90fe; background-image: linear-gradient(top,#4d90fe,#4787ed); text-decoration: none; display:inline-block; height: 27px; padding-left: 8px; padding-right: 8px; line-height: 27px; border-radius: 2px; border-width: 1px;\" target=\"_blank\">\n<span style=\"color: white;\">\n    \n      Reset password\n    \n  </span>\n</a>\n<br/>\n<br/>\n                \n                  Sincerely,<br/>\n                  The Google Accounts team\n                \n                </td>\n<td style=\"border-top: none; border-bottom: none; border-left: none; border-right: none;\" width=\"15\">\n</td>\n</tr>\n<tr>\n<td height=\"15\" style=\"border-top: none; border-bottom: none; border-left: none; border-right: none;\">\n</td>\n</tr>\n<tr>\n<td style=\"border-top: none; border-bottom: none; border-left: none; border-right: none;\" width=\"15\"></td>\n<td style=\"font-size: 11px; font-family: arial, sans-serif; color: #777777; border-top: none; border-bottom: none; border-left: none; border-right: none;\" width=\"568\">\n                \n                  This email can\'t receive replies. For more information, visit the <a href=\"https://support.google.com/accounts/bin/answer.py?answer=2450236\" style=\"text-decoration: none; color: #4D90FE\"><span style=\"color: #4D90FE;\">Google Accounts Help Center</span></a>.\n                \n                </td>\n<td style=\"border-top: none; border-bottom: none; border-left: none; border-right: none;\" width=\"15\"></td>\n</tr>\n<tr>\n<td height=\"15\" style=\"border-top: none; border-bottom: none; border-left: none; border-right: none;\">\n</td>\n</tr>\n</table>\n<table bgcolor=\"#f1f1f1\" height=\"80\" style=\"text-align: left\">\n<tr valign=\"middle\">\n<td style=\"font-size: 11px; font-family: arial, sans-serif; color: #777777;\">\n                  \n                    You received this mandatory email service announcement to update you about important changes to your Google product or account.\n                  \n                  <br/>\n<br/>\n<div style=\"direction: ltr;\">\n                  \n                    ¬© 2013 Google Inc., 1600 Amphitheatre Parkway, Mountain View, CA 94043, USA\n                  \n                  </div>\n</td>\n</tr>\n</table>\n</td>\n</tr>\n</table>\n</body></html>','\n \n \n \n \n \n \n \n \n \n \n            \n              Inbox App\n            \n           \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n            \n              Hi Inbox,\n               \n \n            \n\n\nThe recove',0,1449471921372979402,1449471921372979402,NULL,'[]','message','2014-05-13 02:19:13','2014-08-27 01:13:29',NULL,0,0,0,NULL,NULL,NULL,0,NULL),(11,'‰•™+%ÔøΩFÔøΩÔøΩÔ',11,'[[\"Inbox App\", \"inboxapptest@gmail.com\"]]','[]','[]','[[\"\\u2605The red-haired mermaid\\u2605\", \"inboxapptest@gmail.com\"]]','[[\"\", \"ben.bitdiddle1861@gmail.com\"]]','[]',NULL,'<5361906e.c3ef320a.62fb.064c@mx.google.com>','Wakeup78fcb997159345c9b160573e1887264a','2014-05-01 00:08:14',1238,'aa2f127af89b74364ae781becd35704c48f690a3df0abd90e543eafc2ef4d590',0,'<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>','Sea, birds, yoga and sand.',0,1466856002099058157,1466856002099058157,'c64be65384804950972d7cb34cd33c69','[]','message','2014-05-13 02:19:13','2014-08-27 01:13:29',NULL,0,0,0,NULL,NULL,NULL,0,NULL),(12,'\0BÔøΩs“ùM ÔøΩÔøΩ',12,'[[\"Inbox App\", \"inboxapptest@gmail.com\"]]','[]','[]','[[\"\\u2605The red-haired mermaid\\u2605\", \"inboxapptest@gmail.com\"]]','[[\"\", \"ben.bitdiddle1861@gmail.com\"]]','[]',NULL,'<53618e85.e14f320a.1f54.21a6@mx.google.com>','Wakeup1dd3dabe7d9444da8aec3be27a82d030','2014-05-01 00:00:05',1199,'4a07bb7d5d933c811c267c0262525de7c468d735e9b6edb0ee2060b6f24ab330',0,'<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>','Sea, birds, yoga and sand.',0,1466855488650356657,1466855488650356657,'e4f72ba9f22842bab7d41e6c4b877b83','[]','message','2014-05-13 02:19:13','2014-08-27 01:13:29',NULL,0,0,0,NULL,NULL,NULL,0,NULL),(13,'ÔøΩÔøΩÔøΩÔøΩÔøΩÔ',13,'[[\"Inbox App\", \"inboxapptest@gmail.com\"]]','[]','[]','[[\"\\u2605The red-haired mermaid\\u2605\", \"inboxapptest@gmail.com\"]]','[[\"\", \"ben.bitdiddle1861@gmail.com\"]]','[]',NULL,'<53618c4e.a983320a.45a5.21a5@mx.google.com>','Wakeupe2ea85dc880d421089b7e1fb8cc12c35','2014-04-30 23:50:38',1200,'91b33ba2f89ca4006d4b5c26d760d4e253bb3f4ed5c87efe964545c2c4ca0db4',0,'<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>','Sea, birds, yoga and sand.',0,1466854894292093968,1466854894292093968,'d1dea076298a4bd09178758433f7542c','[]','message','2014-05-13 02:19:13','2014-08-27 01:13:29',NULL,0,0,0,NULL,NULL,NULL,0,NULL),(14,'ÔøΩoÔøΩ)aA⁄§TÔø',14,'[[\"Inbox App\", \"inboxapptest@gmail.com\"]]','[]','[]','[[\"\\u2605The red-haired mermaid\\u2605\", \"inboxapptest@gmail.com\"]]','[[\"\", \"ben.bitdiddle1861@gmail.com\"]]','[]',NULL,'<536030e2.640e430a.04ce.ffff8de9@mx.google.com>','Wakeup735d8864f6124797a10e94ec5de6be13','2014-04-29 23:08:18',1205,'73b93d369f20843a12a81daf72788b1b7fbe703c4abd289f69d1e41f212833a0',0,'<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>','Sea, birds, yoga and sand.',0,1466761634398434761,1466761634398434761,'5bf16c2bc9684717a9b77b73cbe9ba45','[]','message','2014-05-13 02:19:13','2014-08-27 01:13:29',NULL,0,0,0,NULL,NULL,NULL,0,NULL),(15,'ÔøΩÔøΩÔøΩÔøΩG^',15,'[[\"Inbox App\", \"inboxapptest@gmail.com\"]]','[]','[]','[[\"\\u2605The red-haired mermaid\\u2605\", \"inboxapptest@gmail.com\"]]','[[\"\", \"ben.bitdiddle1861@gmail.com\"]]','[]',NULL,'<53602f7d.a6a3420a.73de.6c0b@mx.google.com>','Wakeup2eba715ecd044a55ae4e12f604a8dc96','2014-04-29 23:02:21',1242,'b13ddac39e20275606cf2f651e269f22f850ac18dce43cf18de982ed3ac20e4f',0,'<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>','Sea, birds, yoga and sand.',0,1466761259745473801,1466761259745473801,'7e7d36a5b6f54af1af551a55b48d1735','[]','message','2014-05-13 02:19:13','2014-08-27 01:13:29',NULL,0,0,0,NULL,NULL,NULL,0,NULL),(16,'ÔøΩÔøΩÔøΩ>ﬂ§GÔøΩ',16,'[[\"kavya joshi\", \"kavya719@gmail.com\"]]','[]','[]','[[\"\", \"inboxapptest@gmail.com\"]]','[]','[]','\"<2D4C6F7D-59F9-4B12-8BEF-3C60556AEC7E@gmail.com>\"','<CAMpoCYqq6BmoRW+MouXOwDxiA=DO20b=sG4e2agmr04Bt8Wg_g@mail.gmail.com>','Golden Gate Park next Sat','2014-04-24 08:58:04',13142,'a5993aef718c4ce3ffd93f0a3cf3a4e54f93278bcb5873a533de3882c383e706',0,'<html><body><div dir=\"ltr\"><br/><br/><br/></div></body></html>','',0,1466255156975764289,1466255156975764289,NULL,'[\"<CA+ADUwxeXG8+=Mya+T1Qb_RYS23w6=_EZgssm3GgW6SkhXPxGQ@mail.gmail.com>\", \"<F7C679E5-09F7-4F17-B1CA-A67A6B207650@gmail.com>\", \"<CAPGJ9TSw5oHjhDNGNa3zs4GQ1WC=bCJ8UTdF12NFqgSdYib9FA@mail.gmail.com>\", \"<CAPGJ9TRPNG7pS0JTEZog1A+usobFsH3S5nE0EbPbqtwBW3dKKw@mail.gmail.com>\", \"<CA+ADUwytg_oZ6B2HfW=v=Vy39G1t1vT17UpjUTaYJuqr8FYR6w@mail.gmail.com>\", \"<CALEp7UFOAXWGgMUW9_GVmJfd1xQSfmXHoGs3rajEd6wZwra1Qw@mail.gmail.com>\", \"<CA+ADUwwh7gmTDfzVObOkcm0d=5j9mMZt-NxswDqXv9VnpYg_Lg@mail.gmail.com>\", \"<CAMpoCYqjMdo=dVvQMZZE5BhZMb2sZkznQnc=7K6kZ_M6NCg+EQ@mail.gmail.com>\", \"<CAPGJ9TQi7Rqxr+HmjASJJ0o2OMgFBG5z-mguUQuy8su1fakLiQ@mail.gmail.com>\", \"<CA+ADUwzEgH6GC=ji5FT0m+i1XSxu0uamwrqAwGMAZhg-qWvL2g@mail.gmail.com>\", \"<CAPGJ9TQkb923ZKeVxqfqB=JeLnhE9-MOAigRrHo-PZCtueZ-Tg@mail.gmail.com>\", \"<3A2441BA-C669-4533-A67A-5CE841A82B54@gmail.com>\", \"<CALEp7UFN3t=rzzZ_in=3LvAypVN=S9hi_RQkpKwc1kc13ymYTw@mail.gmail.com>\", \"<CALRhdLLxFd1L5D+7RoUKVqq0G62cLJezYmMZaST2eiB7kQDCPw@mail.gmail.com>\", \"<CAPGJ9TQe4TyhwmS3vbu1hkZgDkNzsb4O2F1OYvvhMxO3v61Ehg@mail.gmail.com>\", \"<2D4C6F7D-59F9-4B12-8BEF-3C60556AEC7E@gmail.com>\"]','message','2014-05-13 02:19:13','2014-08-27 01:13:29',NULL,1,0,0,NULL,NULL,NULL,0,NULL);
/*!40000 ALTER TABLE `message` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `messagecontactassociation`
--

DROP TABLE IF EXISTS `messagecontactassociation`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `messagecontactassociation` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `contact_id` int(11) NOT NULL,
  `message_id` int(11) NOT NULL,
  `field` enum('from_addr','to_addr','cc_addr','bcc_addr') DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`,`contact_id`,`message_id`),
  KEY `contact_id` (`contact_id`),
  KEY `message_id` (`message_id`),
  KEY `ix_messagecontactassociation_created_at` (`created_at`),
  KEY `ix_messagecontactassociation_deleted_at` (`deleted_at`),
  KEY `ix_messagecontactassociation_updated_at` (`updated_at`),
  CONSTRAINT `messagecontactassociation_ibfk_2` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`) ON DELETE CASCADE,
  CONSTRAINT `messagecontactassociation_ibfk_1` FOREIGN KEY (`contact_id`) REFERENCES `contact` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=39 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `messagecontactassociation`
--

LOCK TABLES `messagecontactassociation` WRITE;
/*!40000 ALTER TABLE `messagecontactassociation` DISABLE KEYS */;
INSERT INTO `messagecontactassociation` VALUES (1,1,1,'to_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(2,2,1,'from_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(3,3,2,'to_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(4,4,2,'cc_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(5,4,2,'from_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(6,1,3,'to_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(7,5,3,'from_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(8,1,4,'to_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(9,6,4,'from_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(10,1,5,'to_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(11,2,5,'from_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(12,1,6,'to_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(13,2,6,'from_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(14,1,7,'to_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(15,2,7,'from_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(16,1,8,'to_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(17,2,8,'from_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(18,1,9,'to_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(19,2,9,'from_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(20,1,10,'to_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(21,7,10,'from_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(22,1,11,'to_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(23,2,11,'cc_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(24,1,11,'from_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(25,1,12,'to_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(26,2,12,'cc_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(27,1,12,'from_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(28,1,13,'to_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(29,2,13,'cc_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(30,1,13,'from_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(31,1,14,'to_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(32,2,14,'cc_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(33,1,14,'from_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(34,1,15,'to_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(35,2,15,'cc_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(36,1,15,'from_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(37,1,16,'to_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(38,8,16,'from_addr','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL);
/*!40000 ALTER TABLE `messagecontactassociation` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `namespace`
--

DROP TABLE IF EXISTS `namespace`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `namespace` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `public_id` binary(16) NOT NULL,
  `account_id` int(11) DEFAULT NULL,
  `type` enum('root','shared_folder') NOT NULL DEFAULT 'root',
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `account_id` (`account_id`),
  KEY `ix_namespace_public_id` (`public_id`),
  KEY `ix_namespace_created_at` (`created_at`),
  KEY `ix_namespace_deleted_at` (`deleted_at`),
  KEY `ix_namespace_updated_at` (`updated_at`),
  CONSTRAINT `namespace_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `namespace`
--

LOCK TABLES `namespace` WRITE;
/*!40000 ALTER TABLE `namespace` DISABLE KEYS */;
INSERT INTO `namespace` VALUES (1,'>ÔøΩÔøΩÔøΩfÔøΩ@Ô',1,'root','2014-05-13 02:19:13','2014-05-13 02:19:13',NULL);
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
  `refresh_token_id` int(11) DEFAULT NULL,
  `scope` varchar(512) DEFAULT NULL,
  `locale` varchar(8) DEFAULT NULL,
  `client_id` varchar(256) DEFAULT NULL,
  `client_secret` varchar(256) DEFAULT NULL,
  `o_id` varchar(32) DEFAULT NULL,
  `o_id_token` varchar(1024) DEFAULT NULL,
  `link` varchar(256) DEFAULT NULL,
  `name` varchar(256) DEFAULT NULL,
  `gender` varchar(16) DEFAULT NULL,
  `family_name` varchar(256) DEFAULT NULL,
  `given_name` varchar(256) DEFAULT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `outlookaccount_ibfk_1` FOREIGN KEY (`id`) REFERENCES `imapaccount` (`id`) ON DELETE CASCADE
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
  `id` int(11) NOT NULL,
  `message_id` int(11) DEFAULT NULL,
  `walk_index` int(11) DEFAULT NULL,
  `content_disposition` enum('inline','attachment') DEFAULT NULL,
  `content_id` varchar(255) DEFAULT NULL,
  `is_inboxapp_attachment` tinyint(1) DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `message_id` (`message_id`,`walk_index`),
  CONSTRAINT `part_ibfk_1` FOREIGN KEY (`id`) REFERENCES `block` (`id`) ON DELETE CASCADE,
  CONSTRAINT `part_ibfk_2` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `part`
--

LOCK TABLES `part` WRITE;
/*!40000 ALTER TABLE `part` DISABLE KEYS */;
INSERT INTO `part` VALUES (1,1,0,NULL,NULL,0),(2,1,1,NULL,NULL,0),(3,1,2,NULL,NULL,0),(4,2,0,NULL,NULL,0),(5,2,1,NULL,NULL,0),(6,2,2,NULL,NULL,0),(7,3,0,NULL,NULL,0),(8,3,1,NULL,NULL,0),(9,3,2,NULL,NULL,0),(10,4,0,NULL,NULL,0),(11,4,1,NULL,NULL,0),(12,4,2,NULL,NULL,0),(13,5,0,NULL,NULL,0),(14,5,1,NULL,NULL,0),(15,5,2,NULL,NULL,0),(16,6,0,NULL,NULL,0),(17,6,1,NULL,NULL,0),(18,6,2,NULL,NULL,0),(19,7,0,NULL,NULL,0),(20,7,1,NULL,NULL,0),(21,7,2,NULL,NULL,0),(22,8,0,NULL,NULL,0),(23,8,1,NULL,NULL,0),(24,8,2,NULL,NULL,0),(25,9,0,NULL,NULL,0),(26,9,1,NULL,NULL,0),(27,9,2,NULL,NULL,0),(28,10,0,NULL,NULL,0),(29,10,2,NULL,NULL,0),(30,10,3,NULL,NULL,0),(31,10,4,'attachment','<google>',0),(32,10,5,'attachment','<profilephoto>',0),(33,11,0,NULL,NULL,0),(34,11,1,NULL,NULL,0),(35,11,2,NULL,NULL,0),(36,12,0,NULL,NULL,0),(37,12,1,NULL,NULL,0),(38,12,2,NULL,NULL,0),(39,13,0,NULL,NULL,0),(40,13,1,NULL,NULL,0),(41,13,2,NULL,NULL,0),(42,14,0,NULL,NULL,0),(43,14,1,NULL,NULL,0),(44,14,2,NULL,NULL,0),(45,15,0,NULL,NULL,0),(46,15,1,NULL,NULL,0),(47,15,2,NULL,NULL,0),(48,16,0,NULL,NULL,0),(49,16,1,NULL,NULL,0),(50,16,2,NULL,NULL,0);
/*!40000 ALTER TABLE `part` ENABLE KEYS */;
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
  `acl_id` int(11) NOT NULL,
  `type` int(11) NOT NULL,
  `secret` varchar(2048) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `secret`
--

LOCK TABLES `secret` WRITE;
/*!40000 ALTER TABLE `secret` DISABLE KEYS */;
INSERT INTO `secret` VALUES ('2014-07-09 18:58:49','2014-07-09 18:58:49',NULL,1,0,0,'1/XUcATARUuEjFSFk9M2ZkIHExnCcFCi5E8veIj2jKetA');
/*!40000 ALTER TABLE `secret` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `secrets`
--

DROP TABLE IF EXISTS `secrets`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `secrets` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `acl_id` int(11) NOT NULL,
  `type` int(11) NOT NULL,
  `secret` varchar(512) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `secrets`
--

LOCK TABLES `secrets` WRITE;
/*!40000 ALTER TABLE `secrets` DISABLE KEYS */;
INSERT INTO `secrets` VALUES (1,0,0,'1/XUcATARUuEjFSFk9M2ZkIHExnCcFCi5E8veIj2jKetA');
/*!40000 ALTER TABLE `secrets` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `spoolmessage`
--

DROP TABLE IF EXISTS `spoolmessage`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `spoolmessage` (
  `id` int(11) NOT NULL,
  `created_date` datetime DEFAULT NULL,
  `is_sent` tinyint(1) NOT NULL DEFAULT '0',
  `resolved_message_id` int(11) DEFAULT NULL,
  `parent_draft_id` int(11) DEFAULT NULL,
  `state` enum('draft','sending','sending failed','sent') NOT NULL DEFAULT 'draft',
  `is_reply` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `resolved_message_id` (`resolved_message_id`),
  KEY `spoolmessage_ibfk_3` (`parent_draft_id`),
  CONSTRAINT `spoolmessage_ibfk_1` FOREIGN KEY (`id`) REFERENCES `message` (`id`) ON DELETE CASCADE,
  CONSTRAINT `spoolmessage_ibfk_2` FOREIGN KEY (`resolved_message_id`) REFERENCES `message` (`id`) ON DELETE CASCADE,
  CONSTRAINT `spoolmessage_ibfk_3` FOREIGN KEY (`parent_draft_id`) REFERENCES `spoolmessage` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `spoolmessage`
--

LOCK TABLES `spoolmessage` WRITE;
/*!40000 ALTER TABLE `spoolmessage` DISABLE KEYS */;
/*!40000 ALTER TABLE `spoolmessage` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tag`
--

DROP TABLE IF EXISTS `tag`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tag` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `namespace_id` int(11) NOT NULL,
  `public_id` varchar(191) NOT NULL,
  `name` varchar(191) NOT NULL,
  `user_created` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `namespace_id` (`namespace_id`,`name`),
  UNIQUE KEY `namespace_id_2` (`namespace_id`,`public_id`),
  KEY `ix_tag_created_at` (`created_at`),
  KEY `ix_tag_deleted_at` (`deleted_at`),
  KEY `ix_tag_updated_at` (`updated_at`),
  CONSTRAINT `tag_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tag`
--

LOCK TABLES `tag` WRITE;
/*!40000 ALTER TABLE `tag` DISABLE KEYS */;
INSERT INTO `tag` VALUES (1,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,'replied','replied',0),(2,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,'sending','sending',0),(3,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,'all','all',0),(4,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,'trash','trash',0),(5,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,'drafts','drafts',0),(6,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,'spam','spam',0),(7,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,'unstarred','unstarred',0),(8,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,'send','send',0),(9,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,'inbox','inbox',0),(10,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,'file','file',0),(11,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,'starred','starred',0),(12,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,'unread','unread',0),(13,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,'archive','archive',0),(14,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,'sent','sent',0),(16,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,'important','important',0),(17,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,'unseen','unseen',0),(18,'2014-08-22 21:04:53','2014-08-22 21:04:53',NULL,1,'attachment','attachment',0);
/*!40000 ALTER TABLE `tag` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tagitem`
--

DROP TABLE IF EXISTS `tagitem`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tagitem` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `thread_id` int(11) NOT NULL,
  `tag_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `tag_id` (`tag_id`),
  KEY `thread_id` (`thread_id`),
  KEY `ix_tagitem_created_at` (`created_at`),
  KEY `ix_tagitem_deleted_at` (`deleted_at`),
  KEY `ix_tagitem_updated_at` (`updated_at`),
  CONSTRAINT `tagitem_ibfk_1` FOREIGN KEY (`tag_id`) REFERENCES `tag` (`id`),
  CONSTRAINT `tagitem_ibfk_2` FOREIGN KEY (`thread_id`) REFERENCES `thread` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=38 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tagitem`
--

LOCK TABLES `tagitem` WRITE;
/*!40000 ALTER TABLE `tagitem` DISABLE KEYS */;
INSERT INTO `tagitem` VALUES (1,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,16),(2,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,9),(3,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,1,3),(4,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,2,16),(5,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,2,9),(6,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,2,3),(7,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,3,16),(8,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,3,9),(9,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,3,3),(10,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,4,16),(11,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,4,9),(12,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,4,3),(13,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,5,16),(14,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,5,9),(15,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,5,3),(16,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,6,16),(17,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,6,9),(18,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,6,3),(19,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,7,16),(20,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,7,9),(21,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,7,3),(22,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,8,16),(23,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,8,9),(24,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,8,3),(25,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,9,16),(26,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,9,9),(27,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,9,3),(28,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,10,9),(29,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,10,3),(30,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,11,3),(31,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,12,3),(32,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,13,3),(33,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,14,3),(34,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,15,3),(35,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,16,16),(36,'2014-05-29 20:13:16','2014-05-29 20:13:16',NULL,16,3),(37,'2014-08-22 21:04:54','2014-08-22 21:04:54',NULL,10,18);
/*!40000 ALTER TABLE `tagitem` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `thread`
--

DROP TABLE IF EXISTS `thread`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `thread` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `public_id` binary(16) NOT NULL,
  `subject` varchar(255) DEFAULT NULL,
  `subjectdate` datetime NOT NULL,
  `recentdate` datetime NOT NULL,
  `namespace_id` int(11) NOT NULL,
  `type` varchar(16) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `participants` text,
  `message_public_ids` text,
  `snippet` varchar(191) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_thread_public_id` (`public_id`),
  KEY `ix_thread_namespace_id` (`namespace_id`),
  KEY `ix_thread_created_at` (`created_at`),
  KEY `ix_thread_deleted_at` (`deleted_at`),
  KEY `ix_thread_updated_at` (`updated_at`),
  CONSTRAINT `thread_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `thread`
--

LOCK TABLES `thread` WRITE;
/*!40000 ALTER TABLE `thread` DISABLE KEYS */;
INSERT INTO `thread` VALUES (1,'ÔøΩ◊ÅÔøΩ&ÔøΩBÔøΩ','asiuhdakhsdf','2014-04-03 02:19:42','2014-04-03 02:19:42',1,'imapthread','2014-05-13 02:19:13','2014-07-01 00:05:39',NULL,'[[\"\", \"inboxapptest@gmail.com\"], [\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]]','[\"1cvu2b1nz6dj1hof5wb8hy1nz\"]','iuhasdklfhasdf'),(2,'ÔøΩÔøΩrEL/ÔøΩÔ','[go-nuts] Runtime Panic On Method Call','2014-05-03 00:26:05','2014-05-03 00:26:05',1,'imapthread','2014-05-13 02:19:13','2014-07-01 00:05:39',NULL,'[[\"golang-nuts\", \"golang-nuts@googlegroups.com\"], [\"\'Rui Ueyama\' via golang-nuts\", \"golang-nuts@googlegroups.com\"], [\"Paul Tiseo\", \"paulxtiseo@gmail.com\"]]','[\"78pgxboai332pi9p2smo4db73\"]','I\'d think you\'ll get more help if you can reproduce the issue with smaller code and paste it to Go Playground. \n \n\n--  \nYou received this message because you are subscribed to the Google Grou'),(3,'ÔøΩÔøΩcRÔøΩNÔøΩ','Tips for using Gmail','2013-08-20 18:02:28','2013-08-20 18:02:28',1,'imapthread','2014-05-13 02:19:13','2014-07-01 00:05:39',NULL,'[[\"Gmail Team\", \"mail-noreply@google.com\"], [\"Inbox App\", \"inboxapptest@gmail.com\"]]','[\"e6z2862swmt2bg3f5i1i2op8f\"]','\n \n \n   \n \n \n \n \n   \n \n \n   \n \n \n \n \n   \n \n \n \n \n \n   \n \n \n   \n \n \n \n Hi Inbox\n                     \n \n \n   \n \n \n \n \n \n   \n \n \n \n Tips for using Gmail \n \n \n \n   \n \n \n   \n \n \n \n \n   \n \n \n   \n '),(4,'k\"ÔøΩÔøΩÔøΩ(B)Ôø','trigger poll','2014-03-21 04:53:00','2014-03-21 04:53:00',1,'imapthread','2014-05-13 02:19:13','2014-07-01 00:05:39',NULL,'[[\"\", \"inboxapptest@gmail.com\"], [\"Christine Spang\", \"christine@spang.cc\"]]','[\"464qbswi15o1woaj127sx4n9b\"]','hi'),(5,'ÔøΩÔøΩ#ÔøΩÔøΩÔøΩ','idle trigger','2014-04-03 02:28:34','2014-04-03 02:28:34',1,'imapthread','2014-05-13 02:19:13','2014-07-01 00:05:39',NULL,'[[\"\", \"inboxapptest@gmail.com\"], [\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]]','[\"3ueca9iuk49bxno49wnhobokt\"]','idle trigger'),(6,'ZÔøΩZ~ÔøΩ^BnÔøΩÔ','idle test 123','2014-04-03 03:10:48','2014-04-03 03:10:48',1,'imapthread','2014-05-13 02:19:13','2014-07-01 00:05:39',NULL,'[[\"\", \"inboxapptest@gmail.com\"], [\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]]','[\"e6z2862swr4vymnno8at7fni5\"]','idle test 123'),(7,'ÔøΩÔøΩÔøΩÔøΩ}ND','another idle test','2014-04-03 02:34:43','2014-04-03 02:34:43',1,'imapthread','2014-05-13 02:19:13','2014-07-01 00:05:39',NULL,'[[\"\", \"inboxapptest@gmail.com\"], [\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]]','[\"3fqr02v6yjz39aap1mgsiwk3j\"]','hello'),(8,'ÔøΩRtÔøΩÔøΩE∆í}','ohaiulskjndf','2014-04-03 02:55:54','2014-04-03 02:55:54',1,'imapthread','2014-05-13 02:19:13','2014-07-01 00:05:39',NULL,'[[\"\", \"inboxapptest@gmail.com\"], [\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]]','[\"1oiw07gvq5unsxcu3g0gxyrb1\"]','aoiulhksjndf'),(9,'gWÔøΩÔøΩKlÔøΩ*','guaysdhbjkf','2014-04-03 02:46:00','2014-04-03 02:46:00',1,'imapthread','2014-05-13 02:19:13','2014-07-01 00:05:39',NULL,'[[\"\", \"inboxapptest@gmail.com\"], [\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]]','[\"m7gcpzvkmn2zwoktw3xl3dfj\"]','a8ogysuidfaysogudhkbjfasdf'),(10,'A$YÔøΩOÔøΩÔøΩp','Google Account recovery phone number changed','2013-10-21 02:55:43','2013-10-21 02:55:43',1,'imapthread','2014-05-13 02:19:13','2014-07-01 00:05:39',NULL,'[[\"\", \"inboxapptest@gmail.com\"], [\"\", \"no-reply@accounts.google.com\"]]','[\"4qd8i8xr4udsq27eh8xnwf7i5\"]','\n \n \n \n \n \n \n \n \n \n \n            \n              Inbox App\n            \n           \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n            \n              Hi Inbox,\n               \n \n            \n\n\nThe recove'),(11,'⁄øÔøΩÔøΩÔøΩqHƒ¥Ô','Wakeup78fcb997159345c9b160573e1887264a','2014-05-01 00:08:14','2014-05-01 00:08:14',1,'imapthread','2014-05-13 02:19:13','2014-07-01 00:05:39',NULL,'[[\"\", \"ben.bitdiddle1861@gmail.com\"], [\"\\u2605The red-haired mermaid\\u2605\", \"inboxapptest@gmail.com\"], [\"Inbox App\", \"inboxapptest@gmail.com\"]]','[\"djb98ezfq1wnltt3odwtysu7j\"]','Sea, birds, yoga and sand.'),(12,'m€æÔøΩÔøΩÔøΩL∆óÔ','Wakeup1dd3dabe7d9444da8aec3be27a82d030','2014-05-01 00:00:05','2014-05-01 00:00:05',1,'imapthread','2014-05-13 02:19:13','2014-07-01 00:05:39',NULL,'[[\"\", \"ben.bitdiddle1861@gmail.com\"], [\"\\u2605The red-haired mermaid\\u2605\", \"inboxapptest@gmail.com\"], [\"Inbox App\", \"inboxapptest@gmail.com\"]]','[\"k27yfxslwt6fuur62kyi5rx\"]','Sea, birds, yoga and sand.'),(13,':5|ÔøΩÔøΩC?ÔøΩÔ','Wakeupe2ea85dc880d421089b7e1fb8cc12c35','2014-04-30 23:50:38','2014-04-30 23:50:38',1,'imapthread','2014-05-13 02:19:13','2014-07-01 00:05:39',NULL,'[[\"\", \"ben.bitdiddle1861@gmail.com\"], [\"\\u2605The red-haired mermaid\\u2605\", \"inboxapptest@gmail.com\"], [\"Inbox App\", \"inboxapptest@gmail.com\"]]','[\"e6z2862swr4vyn2474w1fq7zj\"]','Sea, birds, yoga and sand.'),(14,'ÔøΩÔøΩ|ÔøΩGÔøΩ','Wakeup735d8864f6124797a10e94ec5de6be13','2014-04-29 23:08:18','2014-04-29 23:08:18',1,'imapthread','2014-05-13 02:19:13','2014-07-01 00:05:39',NULL,'[[\"\", \"ben.bitdiddle1861@gmail.com\"], [\"\\u2605The red-haired mermaid\\u2605\", \"inboxapptest@gmail.com\"], [\"Inbox App\", \"inboxapptest@gmail.com\"]]','[\"e6z27et1cjsjyw7vgb3e29igv\"]','Sea, birds, yoga and sand.'),(15,'>V+y.3EÔøΩÔøΩÔøΩ','Wakeup2eba715ecd044a55ae4e12f604a8dc96','2014-04-29 23:02:21','2014-04-29 23:02:21',1,'imapthread','2014-05-13 02:19:13','2014-07-01 00:05:39',NULL,'[[\"\", \"ben.bitdiddle1861@gmail.com\"], [\"\\u2605The red-haired mermaid\\u2605\", \"inboxapptest@gmail.com\"], [\"Inbox App\", \"inboxapptest@gmail.com\"]]','[\"e6z2862swm3jr65avpcsdihr2\"]','Sea, birds, yoga and sand.'),(16,'(ÔøΩ5ÔøΩÔøΩr@qÔø','Golden Gate Park next Sat','2014-04-24 08:58:04','2014-04-24 08:58:04',1,'imapthread','2014-05-13 02:19:13','2014-07-01 00:05:39',NULL,'[[\"\", \"inboxapptest@gmail.com\"], [\"kavya joshi\", \"kavya719@gmail.com\"]]','[\"e6z2862swr4vymohzh0wfoo8t\"]','');
/*!40000 ALTER TABLE `thread` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `transaction`
--

DROP TABLE IF EXISTS `transaction`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `transaction` (
  `table_name` varchar(20) NOT NULL,
  `record_id` int(11) NOT NULL,
  `command` enum('insert','update','delete') NOT NULL,
  `delta` longtext,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `namespace_id` int(11) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `public_id` binary(16) NOT NULL,
  `object_public_id` varchar(191) DEFAULT NULL,
  `public_snapshot` longtext,
  `private_snapshot` longtext,
  PRIMARY KEY (`id`),
  KEY `namespace_id` (`namespace_id`),
  KEY `ix_transaction_created_at` (`created_at`),
  KEY `ix_transaction_deleted_at` (`deleted_at`),
  KEY `ix_transaction_updated_at` (`updated_at`),
  KEY `ix_transaction_public_id` (`public_id`),
  KEY `namespace_id_deleted_at` (`namespace_id`,`deleted_at`),
  CONSTRAINT `transaction_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=144 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `transaction`
--

LOCK TABLES `transaction` WRITE;
/*!40000 ALTER TABLE `transaction` DISABLE KEYS */;
INSERT INTO `transaction` VALUES ('part',3,'insert','{\"walk_index\": 2, \"namespace_id\": 1, \"public_id\": \"a5dswfe6mzl9ad0g8mrk399eq\", \"misc_keyval\": [[\"Content-Type\", [\"text/html\", {\"charset\": \"ISO-8859-1\"}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/html\", \"content_id\": null, \"data_sha256\": \"6103eda40adfd98a9e4b4e16ff958e693893f4c37359c76fd9b4e77531a22828\", \"id\": 3, \"filename\": null, \"message_id\": 1, \"size\": 36}',1,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'}ÔøΩ3ÔøΩÔøΩKhÔø',NULL,NULL,NULL),('part',2,'insert','{\"walk_index\": 1, \"namespace_id\": 1, \"public_id\": \"5nrzawkxf1apntb0evw541akg\", \"misc_keyval\": [[\"Content-Type\", [\"text/plain\", {\"charset\": \"ISO-8859-1\"}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/plain\", \"content_id\": null, \"data_sha256\": \"d58d3859935609dd2afe7233c68939cd9cd20ef54e3a61d0442f41fc157fc10d\", \"id\": 2, \"filename\": null, \"message_id\": 1, \"size\": 15}',2,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'.ÔøΩ3ÔøΩ[J=ÔøΩÔ',NULL,NULL,NULL),('folderitem',1,'insert','{\"thread_id\": 1, \"id\": 1, \"folder_name\": \"important\"}',3,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'4ÔøΩÔøΩXÔøΩiNÔøΩ',NULL,NULL,NULL),('message',1,'insert','{\"public_id\": \"1c393pgoea1sqnv4mv1rpux1c\", \"sender_addr\": [], \"thread_id\": 1, \"bcc_addr\": [], \"cc_addr\": [], \"references\": \"\", \"sanitized_body\": \"<html><body><div dir=\\\"ltr\\\">iuhasdklfhasdf</div></body></html>\", \"id\": 1, \"subject\": \"asiuhdakhsdf\", \"g_msgid\": 1464327557735981576, \"from_addr\": [[\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]], \"g_thrid\": 1464327557735981576, \"inbox_uid\": null, \"snippet\": \"iuhasdklfhasdf\", \"message_id_header\": \"<CABO4WuP6D+RUW5T_ZbER9T-O--qYDj_JbgD72RGGfrSkJteQ4Q@mail.gmail.com>\", \"received_date\": {\"$date\": 1396491582000}, \"size\": 2127, \"type\": \"message\", \"to_addr\": [[\"\", \"inboxapptest@gmail.com\"]], \"mailing_list_headers\": {\"List-Id\": null, \"List-Post\": null, \"List-Owner\": null, \"List-Subscribe\": null, \"List-Unsubscribe\": null, \"List-Archive\": null, \"List-Help\": null}, \"in_reply_to\": null, \"is_draft\": false, \"data_sha256\": \"f92545e762b44776e0cb3fdad773f47a563fd5cb72a7fc31c26a2c43cc764343\", \"reply_to\": []}',4,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,']ÔøΩÔøΩÔøΩENÔø',NULL,NULL,NULL),('folderitem',3,'insert','{\"thread_id\": 1, \"id\": 3, \"folder_name\": \"archive\"}',5,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ$tÔøΩwÔøΩAÔøΩ',NULL,NULL,NULL),('folderitem',2,'insert','{\"thread_id\": 1, \"id\": 2, \"folder_name\": \"inbox\"}',6,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩÔøΩBÔøΩ%JÔ',NULL,NULL,NULL),('part',1,'insert','{\"walk_index\": 0, \"namespace_id\": 1, \"public_id\": \"ccylhpm5fvy284raoo34lgut2\", \"_content_type_other\": null, \"_content_type_common\": null, \"data_sha256\": \"1c61dd2b4dd1193911f3aaa63ac0d7d55058d567664cddaab094e59a46cdc59d\", \"id\": 1, \"message_id\": 1, \"size\": 1950}',7,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩuÔøΩ.J5ÔøΩO',NULL,NULL,NULL),('contact',1,'insert','{\"public_id\": \"9fmqsnooedtybo5c3z0clflnc\", \"uid\": {\"$uuid\": \"ac99aa06560442349cccdfb5f41973d1\"}, \"account_id\": 1, \"source\": \"local\", \"score\": 10, \"provider_name\": \"inbox\", \"email_address\": \"inboxapptest@gmail.com\", \"id\": 1, \"name\": \"\"}',8,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩVÔøΩÔøΩLq',NULL,NULL,NULL),('contact',2,'insert','{\"public_id\": \"92jcqqvvaje9akg7kveteaaln\", \"uid\": {\"$uuid\": \"523f7769c26e4728921dffd43e5bb1b4\"}, \"account_id\": 1, \"source\": \"local\", \"score\": 9, \"provider_name\": \"inbox\", \"email_address\": \"benbitdiddle1861@gmail.com\", \"id\": 2, \"name\": \"Ben Bitdiddle\"}',9,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩÔøΩ>ÔøΩÔøΩ',NULL,NULL,NULL),('part',6,'insert','{\"walk_index\": 2, \"namespace_id\": 1, \"public_id\": \"mup7o0q2aqinnisod06d7kto\", \"misc_keyval\": [[\"Content-Type\", [\"text/html\", {\"charset\": \"UTF-8\"}]], [\"Content-Transfer-Encoding\", [\"quoted-printable\", {}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/html\", \"content_id\": null, \"data_sha256\": \"2014eb3bb6de2ecb23151b266a3057be6cf3e9c19659d215b531fcee286a87f5\", \"id\": 6, \"filename\": null, \"message_id\": 2, \"size\": 2120}',10,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩZÔøΩÔøΩEt',NULL,NULL,NULL),('message',2,'insert','{\"public_id\": \"78pdocq8sa8qw4ky77gzxhdl9\", \"sender_addr\": [[\"\", \"golang-nuts@googlegroups.com\"]], \"thread_id\": 2, \"bcc_addr\": [], \"cc_addr\": [[\"golang-nuts\", \"golang-nuts@googlegroups.com\"]], \"references\": \"<1286bda0-97a1-47c4-be2d-93b2640f2435@googlegroups.com>\", \"sanitized_body\": \"<html><body><div dir=\\\"ltr\\\">I\'d think you\'ll get more help if you can reproduce the issue with smaller code and paste it to Go Playground.<div class=\\\"gmail_extra\\\"></div></div>\\n<p></p>\\n\\n-- <br/>\\nYou received this message because you are subscribed to the Google Groups \\\"golang-nuts\\\" group.<br/>\\nTo unsubscribe from this group and stop receiving emails from it, send an email to <a href=\\\"mailto:golang-nuts+unsubscribe@googlegroups.com\\\">golang-nuts+unsubscribe@googlegroups.com</a>.<br/>\\nFor more options, visit <a href=\\\"https://groups.google.com/d/optout\\\">https://groups.google.com/d/optout</a>.<br/></body></html>\", \"id\": 2, \"subject\": \"[go-nuts] Runtime Panic On Method Call\", \"g_msgid\": 1467038319150540079, \"from_addr\": [[\"\'Rui Ueyama\' via golang-nuts\", \"golang-nuts@googlegroups.com\"]], \"g_thrid\": 1467038319150540079, \"inbox_uid\": null, \"snippet\": \"I\'d think you\'ll get more help if you can reproduce the issue with smaller code and paste it to Go Playground. \\n \\n\\n--  \\nYou received this message because you are subscribed to the Google Grou\", \"message_id_header\": \"<CAJENXgt5t4yYJdDuV7m2DKwcDEbsY8TohVWmgmMqhnqC3pGwMw@mail.gmail.com>\", \"received_date\": {\"$date\": 1399076765000}, \"size\": 10447, \"type\": \"message\", \"to_addr\": [[\"Paul Tiseo\", \"paulxtiseo@gmail.com\"]], \"mailing_list_headers\": {\"List-Id\": \"<golang-nuts.googlegroups.com>\", \"List-Post\": \"<http://groups.google.com/group/golang-nuts/post>, <mailto:golang-nuts@googlegroups.com>\", \"List-Owner\": null, \"List-Subscribe\": \"<http://groups.google.com/group/golang-nuts/subscribe>, <mailto:golang-nuts+subscribe@googlegroups.com>\", \"List-Unsubscribe\": \"<http://groups.google.com/group/golang-nuts/subscribe>, <mailto:googlegroups-manage+332403668183+unsubscribe@googlegroups.com>\", \"List-Archive\": \"<http://groups.google.com/group/golang-nuts>\", \"List-Help\": \"<http://groups.google.com/support/>, <mailto:golang-nuts+help@googlegroups.com>\"}, \"in_reply_to\": \"<1286bda0-97a1-47c4-be2d-93b2640f2435@googlegroups.com>\", \"is_draft\": false, \"data_sha256\": \"e317a191277854cb8b88481268940441a065bad48d02d5a477f0564d4cbe5297\", \"reply_to\": [[\"Rui Ueyama\", \"ruiu@google.com\"]]}',11,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'qÔøΩ\nÔøΩÔøΩgBJÔø',NULL,NULL,NULL),('folderitem',6,'insert','{\"thread_id\": 2, \"id\": 6, \"folder_name\": \"archive\"}',12,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'JÔøΩ’•ÔøΩ@KŸõfÔø',NULL,NULL,NULL),('folderitem',4,'insert','{\"thread_id\": 2, \"id\": 4, \"folder_name\": \"important\"}',13,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'HDÔøΩÔøΩ_KÔøΩÔø',NULL,NULL,NULL),('part',4,'insert','{\"walk_index\": 0, \"namespace_id\": 1, \"public_id\": \"6zkps691gu9y2b3dk5zwh7upk\", \"_content_type_other\": null, \"_content_type_common\": null, \"data_sha256\": \"179cd7e3034869737ae02cee0b918fb85f9254ea2fd0c0b3f7b84a32420edebc\", \"id\": 4, \"message_id\": 2, \"size\": 6738}',14,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ\nKÔøΩV\'IÔøΩÔø',NULL,NULL,NULL),('part',5,'insert','{\"walk_index\": 1, \"namespace_id\": 1, \"public_id\": \"eeu7pyr0rpvvnue1nj1rde1dv\", \"misc_keyval\": [[\"Content-Type\", [\"text/plain\", {\"charset\": \"UTF-8\"}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/plain\", \"content_id\": null, \"data_sha256\": \"7fdc6a5d14d7832747b01287f8b7da14bf612e2e100df9df1b4561bcaec8d268\", \"id\": 5, \"filename\": null, \"message_id\": 2, \"size\": 1361}',15,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'/ÔøΩÔøΩAÔøΩBoÔø',NULL,NULL,NULL),('folderitem',5,'insert','{\"thread_id\": 2, \"id\": 5, \"folder_name\": \"inbox\"}',16,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩÔøΩ\'ÔøΩdH<',NULL,NULL,NULL),('contact',3,'insert','{\"public_id\": \"de3rvdrlp4cuksjn9jt33uhg4\", \"uid\": {\"$uuid\": \"0ff751115a7246a4a0d0d1d189422117\"}, \"account_id\": 1, \"source\": \"local\", \"score\": 10, \"provider_name\": \"inbox\", \"email_address\": \"paulxtiseo@gmail.com\", \"id\": 3, \"name\": \"Paul Tiseo\"}',17,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩLÔøΩÔøΩÔøΩ',NULL,NULL,NULL),('contact',4,'insert','{\"public_id\": \"a46s0bayqfw9kihg3i6sss2dm\", \"uid\": {\"$uuid\": \"6840fd7634e34b1ab0a36b797bbf92d7\"}, \"account_id\": 1, \"source\": \"local\", \"score\": 9, \"provider_name\": \"inbox\", \"email_address\": \"golang-nuts@googlegroups.com\", \"id\": 4, \"name\": \"golang-nuts\"}',18,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ/ÔøΩÔøΩQDgÔø',NULL,NULL,NULL),('folderitem',7,'insert','{\"thread_id\": 3, \"id\": 7, \"folder_name\": \"important\"}',19,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'*ÔøΩ6ÔøΩÔøΩÔøΩK?',NULL,NULL,NULL),('part',8,'insert','{\"walk_index\": 1, \"namespace_id\": 1, \"public_id\": \"16ecxuyoazxnhz6msuqcac4bm\", \"misc_keyval\": [[\"Content-Type\", [\"text/plain\", {\"charset\": \"windows-1252\"}]], [\"Content-Transfer-Encoding\", [\"quoted-printable\", {}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/plain\", \"content_id\": null, \"data_sha256\": \"b1558fdb97bc5918be82a7d342358fdd8abaa32cace1c96056319c594af6ddfe\", \"id\": 8, \"filename\": null, \"message_id\": 3, \"size\": 1251}',20,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ3ÔøΩfÔøΩÔøΩJ',NULL,NULL,NULL),('part',9,'insert','{\"walk_index\": 2, \"namespace_id\": 1, \"public_id\": \"7ll34zrterre48tmhvjs18tpr\", \"misc_keyval\": [[\"Content-Type\", [\"text/html\", {\"charset\": \"windows-1252\"}]], [\"Content-Transfer-Encoding\", [\"quoted-printable\", {}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/html\", \"content_id\": null, \"data_sha256\": \"5ef8b7411036839cf82f81125fda1227b56378c14e4d2f2e251aaaa5496062ad\", \"id\": 9, \"filename\": null, \"message_id\": 3, \"size\": 12626}',21,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩÔøΩÔøΩÔøΩÔ',NULL,NULL,NULL),('folderitem',8,'insert','{\"thread_id\": 3, \"id\": 8, \"folder_name\": \"inbox\"}',22,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ\n#ÔøΩÔøΩKÔø',NULL,NULL,NULL),('message',3,'insert','{\"public_id\": \"aowxtw42xdybrxfpkalf7qvki\", \"sender_addr\": [], \"thread_id\": 3, \"bcc_addr\": [], \"cc_addr\": [], \"references\": \"\", \"sanitized_body\": \"<html xmlns=\\\"http://www.w3.org/1999/xhtml\\\"><head><meta content=\\\"text/html;charset=utf-8\\\" http-equiv=\\\"content-type\\\"/><title>Tips for using Gmail</title></head><body link=\\\"#1155CC\\\" marginheight=\\\"0\\\" marginwidth=\\\"0\\\" text=\\\"#444444\\\">\\n<table bgcolor=\\\"#f5f5f5\\\" border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse: collapse;\\\" width=\\\"100%\\\">\\n<tr>\\n<td>\\u00a0</td>\\n<td height=\\\"51\\\" width=\\\"64\\\"><img alt=\\\"\\\" height=\\\"51\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-top-left.png\\\" style=\\\"display:block\\\" width=\\\"64\\\"/></td>\\n<td background=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-top-middle.png\\\" bgcolor=\\\"#f5f5f5\\\" height=\\\"51\\\" valign=\\\"bottom\\\" width=\\\"673\\\">\\n</td>\\n<td height=\\\"51\\\" width=\\\"64\\\"><img alt=\\\"\\\" height=\\\"51\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-top-right.png\\\" style=\\\"display:block\\\" width=\\\"68\\\"/></td>\\n<td>\\u00a0</td>\\n</tr>\\n<tr>\\n<td>\\u00a0</td>\\n<td height=\\\"225\\\" width=\\\"64\\\"><img alt=\\\"\\\" height=\\\"225\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-middle-1-left.png\\\" style=\\\"display:block\\\" width=\\\"64\\\"/></td>\\n<td bgcolor=\\\"#ffffff\\\" valign=\\\"top\\\" width=\\\"668\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse: collapse; \\\" width=\\\"100%\\\">\\n<tr>\\n<td colspan=\\\"3\\\">\\u00a0</td>\\n</tr>\\n<tr>\\n<td align=\\\"center\\\" colspan=\\\"3\\\" height=\\\"50\\\" valign=\\\"bottom\\\"><img alt=\\\"\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/logo.gif\\\" style=\\\"display:block\\\"/></td>\\n</tr>\\n<tr>\\n<td colspan=\\\"3\\\" height=\\\"40\\\">\\u00a0</td>\\n</tr>\\n<tr>\\n<td>\\u00a0</td>\\n<td width=\\\"450\\\">\\n<b>\\n<font color=\\\"#444444\\\" face=\\\"Arial, sans-serif\\\" size=\\\"-1\\\" style=\\\"line-height: 1.4em\\\">\\n<img alt=\\\"\\\" src=\\\"https://ssl.gstatic.com/accounts/services/mail/msa/gmail_icon_small.png\\\" style=\\\"display:block;float:left;margin-top:4px;margin-right:3px;\\\"/>Hi Inbox\\n                    </font>\\n</b>\\n</td>\\n<td>\\u00a0</td>\\n</tr>\\n<tr>\\n<td height=\\\"40\\\" valign=\\\"top\\\">\\n</td></tr>\\n<tr>\\n<td width=\\\"111\\\">\\u00a0</td>\\n<td align=\\\"left\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse: collapse;\\\" width=\\\"540\\\">\\n<tr>\\n<td valign=\\\"top\\\"><font color=\\\"#444444\\\" face=\\\"Arial, sans-serif\\\" size=\\\"+2\\\"><span style=\\\"font-family:Open Sans, Arial, sans-serif; font-size: 25px\\\">Tips for using Gmail</span></font></td>\\n</tr>\\n</table>\\n</td>\\n<td width=\\\"111\\\">\\u00a0</td>\\n</tr>\\n<tr>\\n<td colspan=\\\"3\\\" height=\\\"10\\\">\\u00a0</td>\\n</tr>\\n</table>\\n</td>\\n<td height=\\\"225\\\" width=\\\"64\\\"><img alt=\\\"\\\" height=\\\"225\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-middle-1-right.png\\\" style=\\\"display:block\\\" width=\\\"64\\\"/></td>\\n<td>\\u00a0</td>\\n</tr>\\n<tr>\\n<td>\\u00a0</td>\\n<td height=\\\"950\\\" width=\\\"64\\\"><img alt=\\\"\\\" height=\\\"950\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-middle-2-left.png\\\" style=\\\"display:block\\\" width=\\\"64\\\"/></td>\\n<td align=\\\"center\\\" bgcolor=\\\"#ffffff\\\" valign=\\\"top\\\" width=\\\"668\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse: collapse;\\\" width=\\\"540\\\">\\n<tr>\\n<td align=\\\"left\\\">\\n<img alt=\\\"\\\" src=\\\"https://ssl.gstatic.com/accounts/services/mail/msa/welcome_hangouts.png\\\" style=\\\"display:block\\\"/>\\n</td>\\n<td width=\\\"15\\\"></td>\\n<td align=\\\"left\\\" valign=\\\"middle\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse:collapse;\\\" width=\\\"400\\\">\\n<tr>\\n<td align=\\\"left\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"+1\\\"><span style=\\\"font-family:Arial, sans-serif; font-size: 20px;\\\">Chat right from your inbox</span></font>\\n</td>\\n</tr>\\n<tr>\\n<td height=\\\"10\\\"></td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\" valign=\\\"top\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"-1\\\" style=\\\"line-height:1.4em\\\">Chat with contacts and start video chats with up to 10 people in <a href=\\\"http://www.google.com/+/learnmore/hangouts/?hl=en\\\" style=\\\"text-decoration:none;\\\">Google+ Hangouts</a>.</font>\\n</td>\\n</tr>\\n</table>\\n</td>\\n</tr>\\n<tr>\\n<td colspan=\\\"3\\\" height=\\\"30\\\">\\u00a0</td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\">\\n<img alt=\\\"\\\" src=\\\"https://ssl.gstatic.com/accounts/services/mail/msa/welcome_contacts.png\\\" style=\\\"display:block\\\"/>\\n</td>\\n<td width=\\\"15\\\"></td>\\n<td align=\\\"left\\\" valign=\\\"middle\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse:collapse;\\\" width=\\\"400\\\">\\n<tr>\\n<td align=\\\"left\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"+1\\\"><span style=\\\"font-family:Arial, sans-serif; font-size: 20px;\\\">Bring your email into Gmail</span></font>\\n</td>\\n</tr>\\n<tr>\\n<td height=\\\"10\\\"></td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\" valign=\\\"top\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"-1\\\" style=\\\"line-height:1.4em\\\">You can import your email from other webmail to make the transition to Gmail a bit easier. <a href=\\\"https://support.google.com/mail/answer/164640?hl=en\\\" style=\\\"text-decoration:none;\\\">Learn how.</a></font>\\n</td>\\n</tr>\\n</table>\\n</td>\\n</tr>\\n<tr>\\n<td colspan=\\\"3\\\" height=\\\"30\\\">\\u00a0</td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\">\\n<img alt=\\\"\\\" src=\\\"https://ssl.gstatic.com/mail/welcome/localized/en/welcome_drive.png\\\" style=\\\"display:block\\\"/>\\n</td>\\n<td width=\\\"15\\\"></td>\\n<td align=\\\"left\\\" valign=\\\"middle\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse:collapse;\\\" width=\\\"400\\\">\\n<tr>\\n<td align=\\\"left\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"+1\\\"><span style=\\\"font-family:Arial, sans-serif; font-size: 20px;\\\">Use Google Drive to send large files</span></font>\\n</td>\\n</tr>\\n<tr>\\n<td height=\\\"10\\\"></td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\" valign=\\\"top\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"-1\\\" style=\\\"line-height:1.4em\\\"><a href=\\\"https://support.google.com/mail/answer/2480713?hl=en\\\" style=\\\"text-decoration:none;\\\">Send huge files in Gmail </a>  (up to 10GB) using <a href=\\\"https://drive.google.com/?hl=en\\\" style=\\\"text-decoration:none;\\\">Google Drive</a>. Plus files stored in Drive stay up-to-date automatically so everyone has the most recent version and can access them from anywhere.</font>\\n</td>\\n</tr>\\n</table>\\n</td>\\n</tr>\\n<tr>\\n<td colspan=\\\"3\\\" height=\\\"30\\\">\\u00a0</td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\">\\n<img alt=\\\"\\\" src=\\\"https://ssl.gstatic.com/accounts/services/mail/msa/welcome_storage.png\\\" style=\\\"display:block\\\"/>\\n</td>\\n<td width=\\\"15\\\"></td>\\n<td align=\\\"left\\\" valign=\\\"middle\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse:collapse;\\\" width=\\\"400\\\">\\n<tr>\\n<td align=\\\"left\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"+1\\\"><span style=\\\"font-family:Arial, sans-serif; font-size: 20px;\\\">Save everything</span></font>\\n</td>\\n</tr>\\n<tr>\\n<td height=\\\"10\\\"></td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\" valign=\\\"top\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"-1\\\" style=\\\"line-height:1.4em\\\">With 10GB of space, you\\u2019ll never need to delete an email. Just keep everything and easily find it later.</font>\\n</td>\\n</tr>\\n</table>\\n</td>\\n</tr>\\n<tr>\\n<td colspan=\\\"3\\\" height=\\\"30\\\">\\u00a0</td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\">\\n<img alt=\\\"\\\" src=\\\"https://ssl.gstatic.com/mail/welcome/localized/en/welcome_search.png\\\" style=\\\"display:block\\\"/>\\n</td>\\n<td width=\\\"15\\\"></td>\\n<td align=\\\"left\\\" valign=\\\"middle\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse:collapse;\\\" width=\\\"400\\\">\\n<tr>\\n<td align=\\\"left\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"+1\\\"><span style=\\\"font-family:Arial, sans-serif; font-size: 20px;\\\">Find emails fast</span></font>\\n</td>\\n</tr>\\n<tr>\\n<td height=\\\"10\\\"></td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\" valign=\\\"top\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"-1\\\" style=\\\"line-height:1.4em\\\">With the power of Google Search right in your inbox, you can quickly find the important emails you need with suggestions based on emails, past searches and contacts.</font>\\n</td>\\n</tr>\\n</table>\\n</td>\\n</tr>\\n<tr>\\n<td colspan=\\\"3\\\" height=\\\"30\\\">\\u00a0</td>\\n</tr>\\n</table>\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse: collapse; \\\" width=\\\"500\\\">\\n<tr>\\n<td colspan=\\\"2\\\" height=\\\"40\\\">\\u00a0</td>\\n</tr>\\n<tr>\\n<td rowspan=\\\"2\\\" width=\\\"68\\\"><img alt=\\\"\\\" src=\\\"https://ssl.gstatic.com/accounts/services/mail/msa/gmail_icon_large.png\\\" style=\\\"display:block\\\"/></td>\\n<td align=\\\"left\\\" height=\\\"20\\\" valign=\\\"bottom\\\"><font color=\\\"#444444\\\" face=\\\"Arial, sans-serif\\\" size=\\\"-1\\\">Happy emailing,</font></td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\" valign=\\\"top\\\"><font color=\\\"#444444\\\" face=\\\"Arial, sans-serif\\\" size=\\\"+2\\\"><span style=\\\"font-family:Open Sans, Arial, sans-serif;\\\">The Gmail Team</span></font></td>\\n</tr>\\n<tr>\\n<td colspan=\\\"2\\\" height=\\\"60\\\">\\u00a0</td>\\n</tr>\\n</table>\\n</td>\\n<td height=\\\"950\\\" width=\\\"64\\\"><img alt=\\\"\\\" height=\\\"950\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-middle-2-right.png\\\" style=\\\"display:block\\\" width=\\\"64\\\"/></td>\\n<td>\\u00a0</td>\\n</tr>\\n<tr>\\n<td>\\u00a0</td>\\n<td height=\\\"102\\\" width=\\\"64\\\"><img alt=\\\"\\\" height=\\\"102\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-bottom-left.png\\\" style=\\\"display:block\\\" width=\\\"64\\\"/></td>\\n<td background=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-bottom-middle.png\\\" height=\\\"102\\\" valign=\\\"top\\\" width=\\\"673\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse: collapse; \\\" width=\\\"100%\\\">\\n<tr>\\n<td height=\\\"12\\\"></td>\\n</tr>\\n<tr>\\n<td valign=\\\"bottom\\\">\\n<font color=\\\"#AAAAAA\\\" face=\\\"Arial, sans-serif\\\" size=\\\"-2\\\">\\n                  \\u00a9 2013 Google Inc. 1600 Amphitheatre Parkway, Mountain View, CA 94043\\n                </font>\\n</td>\\n</tr>\\n</table>\\n</td>\\n<td height=\\\"102\\\" width=\\\"64\\\"><img alt=\\\"\\\" height=\\\"102\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-bottom-right.png\\\" style=\\\"display:block\\\" width=\\\"68\\\"/></td>\\n<td>\\u00a0</td>\\n</tr>\\n</table>\\n</body></html>\", \"id\": 3, \"subject\": \"Tips for using Gmail\", \"g_msgid\": 1443911956831022215, \"from_addr\": [[\"Gmail Team\", \"mail-noreply@google.com\"]], \"g_thrid\": 1443911956831022215, \"inbox_uid\": null, \"snippet\": \"\\n \\n \\n \\u00a0 \\n \\n \\n \\n \\n \\u00a0 \\n \\n \\n \\u00a0 \\n \\n \\n \\n \\n \\u00a0 \\n \\n \\n \\n \\n \\n \\u00a0 \\n \\n \\n \\u00a0 \\n \\n \\n \\n Hi Inbox\\n                     \\n \\n \\n \\u00a0 \\n \\n \\n \\n \\n \\n \\u00a0 \\n \\n \\n \\n Tips for using Gmail \\n \\n \\n \\n \\u00a0 \\n \\n \\n \\u00a0 \\n \\n \\n \\n \\n \\u00a0 \\n \\n \\n \\u00a0 \\n \", \"message_id_header\": \"<CAOPuB_MAEq7GsOVvWgE+qHR_6vWYXifHhF+hQ1sFyzk_eKPYpQ@mail.gmail.com>\", \"received_date\": {\"$date\": 1377021748000}, \"size\": 15711, \"type\": \"message\", \"to_addr\": [[\"Inbox App\", \"inboxapptest@gmail.com\"]], \"mailing_list_headers\": {\"List-Id\": null, \"List-Post\": null, \"List-Owner\": null, \"List-Subscribe\": null, \"List-Unsubscribe\": null, \"List-Archive\": null, \"List-Help\": null}, \"in_reply_to\": null, \"is_draft\": false, \"data_sha256\": \"8f62d93f04735652b9f4edc89bc764e5b48fff1bcd0acec67718047c81d76051\", \"reply_to\": []}',23,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'6ÔøΩÔøΩÔøΩ\nÔøΩEÔ',NULL,NULL,NULL),('folderitem',9,'insert','{\"thread_id\": 3, \"id\": 9, \"folder_name\": \"archive\"}',24,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ.ÔøΩÔøΩÔøΩJGÔ',NULL,NULL,NULL),('part',7,'insert','{\"walk_index\": 0, \"namespace_id\": 1, \"public_id\": \"73dkm7j8xewm7c4m93wnu4w9a\", \"_content_type_other\": null, \"_content_type_common\": null, \"data_sha256\": \"98ae516cd24a27e52537143ff996e1c462ae2be9ea96ef0df3e4db41f8cb1060\", \"id\": 7, \"message_id\": 3, \"size\": 453}',25,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ\nÔøΩÔøΩÔøΩ&BU',NULL,NULL,NULL),('contact',1,'update','{\"score\": 11}',26,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'Q\" ÔøΩJÔøΩÔøΩ',NULL,NULL,NULL),('contact',5,'insert','{\"public_id\": \"di10igsxl9uy7c71bcwz05h1j\", \"uid\": {\"$uuid\": \"31d28d8167df479bae796f19589a88dd\"}, \"account_id\": 1, \"source\": \"local\", \"score\": 9, \"provider_name\": \"inbox\", \"email_address\": \"mail-noreply@google.com\", \"id\": 5, \"name\": \"Gmail Team\"}',27,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩÔøΩf1BÔøΩ',NULL,NULL,NULL),('message',4,'insert','{\"public_id\": \"464qbsuwnumipzmfny7kr7rxf\", \"sender_addr\": [[\"\", \"christine.spang@gmail.com\"]], \"thread_id\": 4, \"bcc_addr\": [], \"cc_addr\": [], \"references\": \"\", \"sanitized_body\": \"<html><body><div dir=\\\"ltr\\\">hi</div></body></html>\", \"id\": 4, \"subject\": \"trigger poll\", \"g_msgid\": 1463159441433026019, \"from_addr\": [[\"Christine Spang\", \"christine@spang.cc\"]], \"g_thrid\": 1463159441433026019, \"inbox_uid\": null, \"snippet\": \"hi\", \"message_id_header\": \"<CAFMxqJyA0xft8f67uEcDiTAs8pgfXO26VaipnGHngFB45Vwiog@mail.gmail.com>\", \"received_date\": {\"$date\": 1395377580000}, \"size\": 2178, \"type\": \"message\", \"to_addr\": [[\"\", \"inboxapptest@gmail.com\"]], \"mailing_list_headers\": {\"List-Id\": null, \"List-Post\": null, \"List-Owner\": null, \"List-Subscribe\": null, \"List-Unsubscribe\": null, \"List-Archive\": null, \"List-Help\": null}, \"in_reply_to\": null, \"is_draft\": false, \"data_sha256\": \"6b0736bd5f6e9cb4200e1b280ac649229ee78eae1447028a7489b68739506c3a\", \"reply_to\": []}',28,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'g ßÔøΩmÔøΩ@ÔøΩÔø',NULL,NULL,NULL),('folderitem',10,'insert','{\"thread_id\": 4, \"id\": 10, \"folder_name\": \"important\"}',29,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ9÷¢VÔøΩIUÔøΩ',NULL,NULL,NULL),('folderitem',12,'insert','{\"thread_id\": 4, \"id\": 12, \"folder_name\": \"archive\"}',30,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'/\rÔøΩcD8FÓ≠ÅÔøΩ5',NULL,NULL,NULL),('part',12,'insert','{\"walk_index\": 2, \"namespace_id\": 1, \"public_id\": \"3s8wuv52par00vberkuk85kgj\", \"misc_keyval\": [[\"Content-Type\", [\"text/html\", {\"charset\": \"ISO-8859-1\"}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/html\", \"content_id\": null, \"data_sha256\": \"408ba4f10aada5751a08119a3c82a667239b3094bf14fe2e67a258dc03afbacf\", \"id\": 12, \"filename\": null, \"message_id\": 4, \"size\": 24}',31,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ√úN2BÔøΩxÔø',NULL,NULL,NULL),('part',10,'insert','{\"walk_index\": 0, \"namespace_id\": 1, \"public_id\": \"bwzdk7r5we57dpel296wcf6ln\", \"_content_type_other\": null, \"_content_type_common\": null, \"data_sha256\": \"af620f6b1b2178f7ae978e21534b334c1b313e09c1c9657db686726368312434\", \"id\": 10, \"message_id\": 4, \"size\": 2037}',32,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'=e@ÔøΩ,YCÔøΩÔøΩÔ',NULL,NULL,NULL),('part',11,'insert','{\"walk_index\": 1, \"namespace_id\": 1, \"public_id\": \"5gg7622l7gsovibw5jd5opogl\", \"misc_keyval\": [[\"Content-Type\", [\"text/plain\", {\"charset\": \"ISO-8859-1\"}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/plain\", \"content_id\": null, \"data_sha256\": \"98ea6e4f216f2fb4b69fff9b3a44842c38686ca685f3f55dc48c5d3fb1107be4\", \"id\": 11, \"filename\": null, \"message_id\": 4, \"size\": 3}',33,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩjÔøΩÔøΩ}MÔ',NULL,NULL,NULL),('folderitem',11,'insert','{\"thread_id\": 4, \"id\": 11, \"folder_name\": \"inbox\"}',34,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÏâãÔøΩÔøΩLÔøΩ',NULL,NULL,NULL),('contact',1,'update','{\"score\": 12}',35,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩQÔøΩÔøΩÔøΩ  J',NULL,NULL,NULL),('contact',6,'insert','{\"public_id\": \"5gb3egbwvvh087gnytdb4ud04\", \"uid\": {\"$uuid\": \"c0849c30e29d4404b931ddf9c3d06201\"}, \"account_id\": 1, \"source\": \"local\", \"score\": 9, \"provider_name\": \"inbox\", \"email_address\": \"christine@spang.cc\", \"id\": 6, \"name\": \"Christine Spang\"}',36,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩÔøΩ>‘æC{Ôø',NULL,NULL,NULL),('part',13,'insert','{\"walk_index\": 0, \"namespace_id\": 1, \"public_id\": \"d9u8mcwr689m3y24ygjlohw4l\", \"_content_type_other\": null, \"_content_type_common\": null, \"data_sha256\": \"889b24bb1bf892e1634717a015b0ccd9f93b39afa46a2986be3fe90879d6d19e\", \"id\": 13, \"message_id\": 5, \"size\": 2846}',37,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'qÔøΩWÔøΩZÔøΩNÔø',NULL,NULL,NULL),('message',5,'insert','{\"public_id\": \"3tyqksg3qclys5cpr40mssun1\", \"sender_addr\": [], \"thread_id\": 5, \"bcc_addr\": [], \"cc_addr\": [], \"references\": \"\", \"sanitized_body\": \"<html><body><div dir=\\\"ltr\\\">idle trigger</div></body></html>\", \"id\": 5, \"subject\": \"idle trigger\", \"g_msgid\": 1464328115838585338, \"from_addr\": [[\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]], \"g_thrid\": 1464328115838585338, \"inbox_uid\": null, \"snippet\": \"idle trigger\", \"message_id_header\": \"<CABO4WuM+fcDS9QGXnvOEvm-N8VjF8XxgVLtYLZ0=ENx_0A8u2A@mail.gmail.com>\", \"received_date\": {\"$date\": 1396492114000}, \"size\": 3003, \"type\": \"message\", \"to_addr\": [[\"\", \"inboxapptest@gmail.com\"]], \"mailing_list_headers\": {\"List-Id\": null, \"List-Post\": null, \"List-Owner\": null, \"List-Subscribe\": null, \"List-Unsubscribe\": null, \"List-Archive\": null, \"List-Help\": null}, \"in_reply_to\": null, \"is_draft\": false, \"data_sha256\": \"4461bfa07c3638fa6082535ecb1affb98e3a5a855d32543ac6e7f1d66c95c08e\", \"reply_to\": []}',38,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩÔøΩ\r6ÔøΩL;',NULL,NULL,NULL),('folderitem',15,'insert','{\"thread_id\": 5, \"id\": 15, \"folder_name\": \"archive\"}',39,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'\"t])FjÔøΩ çœ∂Ô',NULL,NULL,NULL),('folderitem',13,'insert','{\"thread_id\": 5, \"id\": 13, \"folder_name\": \"important\"}',40,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'|:ÔøΩÔøΩkEÔøΩÔø',NULL,NULL,NULL),('part',15,'insert','{\"walk_index\": 2, \"namespace_id\": 1, \"public_id\": \"7v9apij58ue792rntg53t2ekj\", \"misc_keyval\": [[\"Content-Type\", [\"text/html\", {\"charset\": \"ISO-8859-1\"}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/html\", \"content_id\": null, \"data_sha256\": \"a0d9bb0476a09e0b8cda7c8799e2ff00959e645292dcd64790d9138623393995\", \"id\": 15, \"filename\": null, \"message_id\": 5, \"size\": 34}',41,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'$hÔøΩNÔøΩL •ÔøΩ',NULL,NULL,NULL),('part',14,'insert','{\"walk_index\": 1, \"namespace_id\": 1, \"public_id\": \"82n7afyko0sdt4xgk0ea8bv5b\", \"misc_keyval\": [[\"Content-Type\", [\"text/plain\", {\"charset\": \"ISO-8859-1\"}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/plain\", \"content_id\": null, \"data_sha256\": \"004815e57fe5989f9536f2d50d29bcc0474462dfd0543868e43c5351285c4f60\", \"id\": 14, \"filename\": null, \"message_id\": 5, \"size\": 13}',42,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩa\r2CRKÔøΩÔøΩZ',NULL,NULL,NULL),('folderitem',14,'insert','{\"thread_id\": 5, \"id\": 14, \"folder_name\": \"inbox\"}',43,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩW~dÔøΩIÔøΩÔ',NULL,NULL,NULL),('contact',1,'update','{\"score\": 13}',44,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'◊∫ÔøΩ[xÔøΩE›åC',NULL,NULL,NULL),('part',16,'insert','{\"walk_index\": 0, \"namespace_id\": 1, \"public_id\": \"7lk6ltkocb1tjfamz1pqttdek\", \"_content_type_other\": null, \"_content_type_common\": null, \"data_sha256\": \"f582e89b834cd098b5d023d09014c99554e519649523427da7eb6ed1bbb2dbb9\", \"id\": 16, \"message_id\": 6, \"size\": 1951}',45,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ\ZA>ÔøΩ@)ÔøΩ',NULL,NULL,NULL),('part',18,'insert','{\"walk_index\": 2, \"namespace_id\": 1, \"public_id\": \"8kxtx92ooontidy3ufzfsun3d\", \"misc_keyval\": [[\"Content-Type\", [\"text/html\", {\"charset\": \"ISO-8859-1\"}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/html\", \"content_id\": null, \"data_sha256\": \"3f93e1bec4711d5bca6c71e1ae3bd7a81437a6ade1e1afab07fd8c26e8f60961\", \"id\": 18, \"filename\": null, \"message_id\": 6, \"size\": 35}',46,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'÷áWÔøΩyB⁄åÔøΩÔø',NULL,NULL,NULL),('message',6,'insert','{\"public_id\": \"ejx6a26qz7hci1ksc4gwscw39\", \"sender_addr\": [], \"thread_id\": 6, \"bcc_addr\": [], \"cc_addr\": [], \"references\": \"\", \"sanitized_body\": \"<html><body><div dir=\\\"ltr\\\">idle test 123</div></body></html>\", \"id\": 6, \"subject\": \"idle test 123\", \"g_msgid\": 1464330773292835572, \"from_addr\": [[\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]], \"g_thrid\": 1464330773292835572, \"inbox_uid\": null, \"snippet\": \"idle test 123\", \"message_id_header\": \"<CABO4WuN+beJ_br_j0uifnXUE+EFAf_bDDBJ0tB-Zkd_2USTc+w@mail.gmail.com>\", \"received_date\": {\"$date\": 1396494648000}, \"size\": 2126, \"type\": \"message\", \"to_addr\": [[\"\", \"inboxapptest@gmail.com\"]], \"mailing_list_headers\": {\"List-Id\": null, \"List-Post\": null, \"List-Owner\": null, \"List-Subscribe\": null, \"List-Unsubscribe\": null, \"List-Archive\": null, \"List-Help\": null}, \"in_reply_to\": null, \"is_draft\": false, \"data_sha256\": \"be9b8517433ab5524b7719653d2a057d1f0e4145b4f111e9e4c83dbab6bd6242\", \"reply_to\": []}',47,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩÔøΩRFMÔø',NULL,NULL,NULL),('folderitem',17,'insert','{\"thread_id\": 6, \"id\": 17, \"folder_name\": \"inbox\"}',48,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'YÔøΩcÔøΩ@ÔøΩCrÔø',NULL,NULL,NULL),('folderitem',18,'insert','{\"thread_id\": 6, \"id\": 18, \"folder_name\": \"archive\"}',49,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩBQ[ÔøΩ:DÔøΩÔø',NULL,NULL,NULL),('part',17,'insert','{\"walk_index\": 1, \"namespace_id\": 1, \"public_id\": \"9ita4einrwv0zrzxswzz7ejc0\", \"misc_keyval\": [[\"Content-Type\", [\"text/plain\", {\"charset\": \"ISO-8859-1\"}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/plain\", \"content_id\": null, \"data_sha256\": \"b0bbbdfc73c7ebd75b9d5e66896312cc3c3a59fe5c86e0de44de3a132b34ebad\", \"id\": 17, \"filename\": null, \"message_id\": 6, \"size\": 14}',50,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'=i8ÔøΩ%EÔøΩÔøΩR',NULL,NULL,NULL),('folderitem',16,'insert','{\"thread_id\": 6, \"id\": 16, \"folder_name\": \"important\"}',51,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩlÔøΩ\"wK»ëÔøΩ',NULL,NULL,NULL),('contact',1,'update','{\"score\": 14}',52,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'XÔøΩÔøΩfÔøΩÔøΩD',NULL,NULL,NULL),('message',7,'insert','{\"public_id\": \"3fqr02v6yjz37rfr902w63tgk\", \"sender_addr\": [], \"thread_id\": 7, \"bcc_addr\": [], \"cc_addr\": [], \"references\": \"\", \"sanitized_body\": \"<html><body><div dir=\\\"ltr\\\">hello</div></body></html>\", \"id\": 7, \"subject\": \"another idle test\", \"g_msgid\": 1464328502421499234, \"from_addr\": [[\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]], \"g_thrid\": 1464328502421499234, \"inbox_uid\": null, \"snippet\": \"hello\", \"message_id_header\": \"<CABO4WuNcTC0_37JuNRQugskTCyYM9-HrszhPKfrf+JqOJE8ntA@mail.gmail.com>\", \"received_date\": {\"$date\": 1396492483000}, \"size\": 2124, \"type\": \"message\", \"to_addr\": [[\"\", \"inboxapptest@gmail.com\"]], \"mailing_list_headers\": {\"List-Id\": null, \"List-Post\": null, \"List-Owner\": null, \"List-Subscribe\": null, \"List-Unsubscribe\": null, \"List-Archive\": null, \"List-Help\": null}, \"in_reply_to\": null, \"is_draft\": false, \"data_sha256\": \"8adff77788264670035888b1cb2afc6edd4a20b50c43f5b11874f2bc84d1c835\", \"reply_to\": []}',53,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,',fÔøΩ#ÔøΩCÔøΩÔø',NULL,NULL,NULL),('folderitem',21,'insert','{\"thread_id\": 7, \"id\": 21, \"folder_name\": \"archive\"}',54,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ﬂç}ÔøΩÔøΩÔøΩNSÔø',NULL,NULL,NULL),('folderitem',20,'insert','{\"thread_id\": 7, \"id\": 20, \"folder_name\": \"inbox\"}',55,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩaﬂÅuM@ øÔøΩ\ZW',NULL,NULL,NULL),('part',19,'insert','{\"walk_index\": 0, \"namespace_id\": 1, \"public_id\": \"17qyhh8lgpw0ytyodxhpkgnep\", \"_content_type_other\": null, \"_content_type_common\": null, \"data_sha256\": \"223681a017f96b40fa854b8810c039a20db392c8df9773575177976aba3e0834\", \"id\": 19, \"message_id\": 7, \"size\": 1965}',56,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ√•\nL~ÔøΩ>|',NULL,NULL,NULL),('part',20,'insert','{\"walk_index\": 1, \"namespace_id\": 1, \"public_id\": \"2qktlwsya5ibd1gwt6cdbry75\", \"misc_keyval\": [[\"Content-Type\", [\"text/plain\", {\"charset\": \"ISO-8859-1\"}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/plain\", \"content_id\": null, \"data_sha256\": \"5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03\", \"id\": 20, \"filename\": null, \"message_id\": 7, \"size\": 6}',57,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩÔøΩÔøΩJÔ',NULL,NULL,NULL),('part',21,'insert','{\"walk_index\": 2, \"namespace_id\": 1, \"public_id\": \"ew61n9u0ongow41dmayeyo7i8\", \"misc_keyval\": [[\"Content-Type\", [\"text/html\", {\"charset\": \"ISO-8859-1\"}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/html\", \"content_id\": null, \"data_sha256\": \"eccf61f9770be39afd1efe2c8ec5bdbf2ddc3d3cf30a688bf6a18bf4dac45048\", \"id\": 21, \"filename\": null, \"message_id\": 7, \"size\": 27}',58,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩBÔøΩÔøΩ@]Ôø',NULL,NULL,NULL),('folderitem',19,'insert','{\"thread_id\": 7, \"id\": 19, \"folder_name\": \"important\"}',59,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩspÔøΩÔøΩ;@∆∫',NULL,NULL,NULL),('contact',1,'update','{\"score\": 15}',60,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ]BHkmKŸÑÔøΩÔø',NULL,NULL,NULL),('part',23,'insert','{\"walk_index\": 1, \"namespace_id\": 1, \"public_id\": \"aljqi080vg3g2e99fhjx8nlo6\", \"misc_keyval\": [[\"Content-Type\", [\"text/plain\", {\"charset\": \"ISO-8859-1\"}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/plain\", \"content_id\": null, \"data_sha256\": \"31b75c53af215582d8b94e90730e58dd711f17b2c6c9128836ba98e8620892c8\", \"id\": 23, \"filename\": null, \"message_id\": 8, \"size\": 13}',61,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩ÷ëÔøΩ\"H(Ôø',NULL,NULL,NULL),('folderitem',24,'insert','{\"thread_id\": 8, \"id\": 24, \"folder_name\": \"archive\"}',62,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ﬂÉÔøΩGI)ÔøΩ3<—',NULL,NULL,NULL),('message',8,'insert','{\"public_id\": \"1ois6b5z3fuczqszu0qxji89p\", \"sender_addr\": [], \"thread_id\": 8, \"bcc_addr\": [], \"cc_addr\": [], \"references\": \"\", \"sanitized_body\": \"<html><body><div dir=\\\"ltr\\\">aoiulhksjndf</div></body></html>\", \"id\": 8, \"subject\": \"ohaiulskjndf\", \"g_msgid\": 1464329835043990839, \"from_addr\": [[\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]], \"g_thrid\": 1464329835043990839, \"inbox_uid\": null, \"snippet\": \"aoiulhksjndf\", \"message_id_header\": \"<CABO4WuOoG=Haky985B_Lx3J0kBo1o8J+2rH87qdpnyHg1+JVJA@mail.gmail.com>\", \"received_date\": {\"$date\": 1396493754000}, \"size\": 2994, \"type\": \"message\", \"to_addr\": [[\"\", \"inboxapptest@gmail.com\"]], \"mailing_list_headers\": {\"List-Id\": null, \"List-Post\": null, \"List-Owner\": null, \"List-Subscribe\": null, \"List-Unsubscribe\": null, \"List-Archive\": null, \"List-Help\": null}, \"in_reply_to\": null, \"is_draft\": false, \"data_sha256\": \"6e4a76ba1ca34b0b4edd2d164229ad9d4b8a5d53ea53dc214799c93b802f2340\", \"reply_to\": []}',63,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'B7ÔøΩÔøΩÔøΩeNDÔø',NULL,NULL,NULL),('part',22,'insert','{\"walk_index\": 0, \"namespace_id\": 1, \"public_id\": \"dzddta75o6reb07yhuhxse0hu\", \"_content_type_other\": null, \"_content_type_common\": null, \"data_sha256\": \"6a10813ed0f5a12fb60a530aed347f74b32c0de65da5f8b4f14cd459469bfb30\", \"id\": 22, \"message_id\": 8, \"size\": 2837}',64,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ{ÔøΩÔøΩÔøΩO',NULL,NULL,NULL),('folderitem',23,'insert','{\"thread_id\": 8, \"id\": 23, \"folder_name\": \"inbox\"}',65,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,']ÔøΩaÔøΩÔøΩDÔøΩ',NULL,NULL,NULL),('folderitem',22,'insert','{\"thread_id\": 8, \"id\": 22, \"folder_name\": \"important\"}',66,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'qÔøΩÔøΩ\ZÔøΩBÔøΩ',NULL,NULL,NULL),('part',24,'insert','{\"walk_index\": 2, \"namespace_id\": 1, \"public_id\": \"cvksynwp4v7uu0irsqkbagol6\", \"misc_keyval\": [[\"Content-Type\", [\"text/html\", {\"charset\": \"ISO-8859-1\"}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/html\", \"content_id\": null, \"data_sha256\": \"889eddcafac71f421c65339c0c38bec66940ffdd76adedce2472a4edf704398d\", \"id\": 24, \"filename\": null, \"message_id\": 8, \"size\": 34}',67,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'|ÔøΩÔøΩÔøΩÔøΩN∆',NULL,NULL,NULL),('contact',1,'update','{\"score\": 16}',68,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩÔøΩ-ÔøΩK',NULL,NULL,NULL),('part',27,'insert','{\"walk_index\": 2, \"namespace_id\": 1, \"public_id\": \"bkeoyvyzdrq9wz3l4vneejr8a\", \"misc_keyval\": [[\"Content-Type\", [\"text/html\", {\"charset\": \"ISO-8859-1\"}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/html\", \"content_id\": null, \"data_sha256\": \"d560107b9f59d09cabcbc2633bbf986545e2bd41f3517655d7b8bf3c7dea7786\", \"id\": 27, \"filename\": null, \"message_id\": 9, \"size\": 63}',69,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩp\"ÔøΩx+BÔøΩÔ',NULL,NULL,NULL),('message',9,'insert','{\"public_id\": \"m7gc8epgseemesuizweahmfq\", \"sender_addr\": [], \"thread_id\": 9, \"bcc_addr\": [], \"cc_addr\": [], \"references\": \"\", \"sanitized_body\": \"<html><body><div dir=\\\"ltr\\\">a8ogysuidfaysogudhkbjfasdf<div><br/></div></div></body></html>\", \"id\": 9, \"subject\": \"guaysdhbjkf\", \"g_msgid\": 1464329212533881603, \"from_addr\": [[\"Ben Bitdiddle\", \"ben.bitdiddle1861@gmail.com\"]], \"g_thrid\": 1464329212533881603, \"inbox_uid\": null, \"snippet\": \"a8ogysuidfaysogudhkbjfasdf\", \"message_id_header\": \"<CABO4WuM6jXXOtc7KGU-M4bQKkP3wXxjnrBWFhbznsJDsiauHmA@mail.gmail.com>\", \"received_date\": {\"$date\": 1396493160000}, \"size\": 2165, \"type\": \"message\", \"to_addr\": [[\"\", \"inboxapptest@gmail.com\"]], \"mailing_list_headers\": {\"List-Id\": null, \"List-Post\": null, \"List-Owner\": null, \"List-Subscribe\": null, \"List-Unsubscribe\": null, \"List-Archive\": null, \"List-Help\": null}, \"in_reply_to\": null, \"is_draft\": false, \"data_sha256\": \"e5cc414d931127db23a633eb27b12b1fa7621562ee639487b20c18818cb78437\", \"reply_to\": []}',70,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ\"\0ÔøΩ%ÔøΩDEÔø',NULL,NULL,NULL),('folderitem',27,'insert','{\"thread_id\": 9, \"id\": 27, \"folder_name\": \"archive\"}',71,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'^ÔøΩÔøΩÔøΩZMÔøΩ',NULL,NULL,NULL),('part',26,'insert','{\"walk_index\": 1, \"namespace_id\": 1, \"public_id\": \"bzn56f396mgwi69xsitc7q06r\", \"misc_keyval\": [[\"Content-Type\", [\"text/plain\", {\"charset\": \"ISO-8859-1\"}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/plain\", \"content_id\": null, \"data_sha256\": \"a87dd39d644c9330f2f60ea9458b35c503352a3d6a9be0339f5b3b44d8239d88\", \"id\": 26, \"filename\": null, \"message_id\": 9, \"size\": 27}',72,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ[ÔøΩÔøΩÔøΩ3NÔ',NULL,NULL,NULL),('folderitem',25,'insert','{\"thread_id\": 9, \"id\": 25, \"folder_name\": \"important\"}',73,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩ+ÔøΩÔøΩpCI',NULL,NULL,NULL),('folderitem',26,'insert','{\"thread_id\": 9, \"id\": 26, \"folder_name\": \"inbox\"}',74,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ZÔøΩÔøΩÔøΩVJOÔø',NULL,NULL,NULL),('part',25,'insert','{\"walk_index\": 0, \"namespace_id\": 1, \"public_id\": \"7ohzr8mnpeipdy49220gppi1g\", \"_content_type_other\": null, \"_content_type_common\": null, \"data_sha256\": \"46866e65955fdb44934bda5241facc2e5351d85bc58d5fe4363bacd99dfbed9b\", \"id\": 25, \"message_id\": 9, \"size\": 1949}',75,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩE3ÔøΩÔøΩGWÔø',NULL,NULL,NULL),('contact',1,'update','{\"score\": 17}',76,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'`ÔøΩÔøΩÔøΩÔøΩE“',NULL,NULL,NULL),('part',30,'insert','{\"walk_index\": 3, \"namespace_id\": 1, \"public_id\": \"au4mckfefae6a41wglfyct7d9\", \"misc_keyval\": [[\"Content-Type\", [\"text/html\", {\"charset\": \"ISO-8859-1\"}]], [\"Content-Transfer-Encoding\", [\"quoted-printable\", {}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/html\", \"content_id\": null, \"data_sha256\": \"e956c365e2a7b8481070dde8bdd3d741d799f32f2c208a44a8b6aac9c377419a\", \"id\": 30, \"filename\": null, \"message_id\": 10, \"size\": 5575}',77,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩmhÔøΩ\rA€Ø\n',NULL,NULL,NULL),('folderitem',28,'insert','{\"thread_id\": 10, \"id\": 28, \"folder_name\": \"inbox\"}',78,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'3_L9dHÔøΩÔøΩ\0Ôø',NULL,NULL,NULL),('part',28,'insert','{\"walk_index\": 0, \"namespace_id\": 1, \"public_id\": \"cl2vbhbrfbmchgutyg3kcqbuf\", \"_content_type_other\": null, \"_content_type_common\": null, \"data_sha256\": \"f9f27dc47aa42dcd7dc0140be6723e58942ae5f4b5a4947ff43d8c427991917c\", \"id\": 28, \"message_id\": 10, \"size\": 2224}',79,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩuÔøΩÔøΩÔøΩÔøΩ',NULL,NULL,NULL),('part',32,'insert','{\"walk_index\": 5, \"namespace_id\": 1, \"public_id\": \"ej0vssrsaddtidsfrelsavift\", \"misc_keyval\": [[\"Content-Type\", [\"image/png\", {\"name\": \"profilephoto.png\"}]], [\"Content-Disposition\", [\"attachment\", {\"filename\": \"profilephoto.png\"}]], [\"Content-Transfer-Encoding\", [\"base64\", {}]], [\"Content-Id\", \"<profilephoto>\"]], \"_content_type_other\": null, \"_content_type_common\": \"image/png\", \"content_id\": \"<profilephoto>\", \"data_sha256\": \"ff3f6b9d30f972e18d28a27d9c19aee77c5f704de8cf490a502c1389c2caf93a\", \"id\": 32, \"filename\": \"profilephoto.png\", \"content_disposition\": \"attachment\", \"message_id\": 10, \"size\": 565}',80,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'N(OM*HÔøΩÔøΩ?Ôø',NULL,NULL,NULL),('part',29,'insert','{\"walk_index\": 2, \"namespace_id\": 1, \"public_id\": \"c6fl5i9mbrbcrwwn9inpwfbwm\", \"misc_keyval\": [[\"Content-Type\", [\"text/plain\", {\"format\": \"flowed\", \"charset\": \"ISO-8859-1\", \"delsp\": \"yes\"}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/plain\", \"content_id\": null, \"data_sha256\": \"3d747459c9884417e66ceb56b4f1811b15cfb3fc8efcf1bfb4ac88e3859fa4f0\", \"id\": 29, \"filename\": null, \"message_id\": 10, \"size\": 993}',81,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩTÔøΩZÔøΩEÔø',NULL,NULL,NULL),('part',31,'insert','{\"walk_index\": 4, \"namespace_id\": 1, \"public_id\": \"2kumywaetaego8caxg47xe9f3\", \"misc_keyval\": [[\"Content-Type\", [\"image/png\", {\"name\": \"google.png\"}]], [\"Content-Disposition\", [\"attachment\", {\"filename\": \"google.png\"}]], [\"Content-Transfer-Encoding\", [\"base64\", {}]], [\"Content-Id\", \"<google>\"]], \"_content_type_other\": null, \"_content_type_common\": \"image/png\", \"content_id\": \"<google>\", \"data_sha256\": \"2991102bf5c783ea6f018731a8939ee97a4d7562a76e8188775447e3c6e0876f\", \"id\": 31, \"filename\": \"google.png\", \"content_disposition\": \"attachment\", \"message_id\": 10, \"size\": 6321}',82,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'VcR\"ÔøΩEﬂ°IÔøΩÔ',NULL,NULL,NULL),('message',10,'insert','{\"public_id\": \"4pg72e80db49823fwyibgvezq\", \"sender_addr\": [], \"thread_id\": 10, \"bcc_addr\": [], \"cc_addr\": [], \"references\": \"\", \"sanitized_body\": \"<html lang=\\\"en\\\"><body style=\\\"margin:0; padding: 0;\\\">\\n<table align=\\\"center\\\" bgcolor=\\\"#f1f1f1\\\" border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" height=\\\"100%\\\" style=\\\"border-collapse: collapse\\\" width=\\\"100%\\\">\\n<tr align=\\\"center\\\">\\n<td valign=\\\"top\\\">\\n<table bgcolor=\\\"#f1f1f1\\\" border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" height=\\\"60\\\" style=\\\"border-collapse: collapse\\\">\\n<tr height=\\\"40\\\" valign=\\\"middle\\\">\\n<td width=\\\"9\\\"></td>\\n<td valign=\\\"middle\\\" width=\\\"217\\\">\\n<img alt=\\\"Google Accounts\\\" border=\\\"0\\\" height=\\\"40\\\" src=\\\"cid:google\\\" style=\\\"display: block;\\\"/>\\n</td>\\n<td style=\\\"font-size: 13px; font-family: arial, sans-serif; color: #777777; text-align: right\\\" width=\\\"327\\\">\\n            \\n              Inbox App\\n            \\n          </td>\\n<td width=\\\"10\\\"></td>\\n<td><img src=\\\"cid:profilephoto\\\"/></td>\\n<td width=\\\"10\\\"></td>\\n</tr>\\n</table>\\n<table bgcolor=\\\"#ffffff\\\" border=\\\"1\\\" bordercolor=\\\"#e5e5e5\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"text-align: left\\\">\\n<tr>\\n<td height=\\\"15\\\" style=\\\"border-top: none; border-bottom: none; border-left: none; border-right: none;\\\">\\n</td>\\n</tr>\\n<tr>\\n<td style=\\\"border-top: none; border-bottom: none; border-left: none; border-right: none;\\\" width=\\\"15\\\">\\n</td>\\n<td style=\\\"font-size: 83%; border-top: none; border-bottom: none; border-left: none; border-right: none; font-size: 13px; font-family: arial, sans-serif; color: #222222; line-height: 18px\\\" valign=\\\"top\\\" width=\\\"568\\\">\\n            \\n              Hi Inbox,\\n              <br/>\\n<br/>\\n            \\n\\n\\nThe recovery phone number for your Google Account - inboxapptest@gmail.com - was recently changed. If you made this change, you don\'t need to do anything more.\\n\\n<br/>\\n<br/>\\n\\nIf you didn\'t change your recovery phone, someone may have broken into your account. Visit this link for more information: <a href=\\\"https://support.google.com/accounts/bin/answer.py?answer=2450236\\\" style=\\\"text-decoration: none; color: #4D90FE\\\">https://support.google.com/accounts/bin/answer.py?answer=2450236</a>.\\n\\n<br/>\\n<br/>\\n\\nIf you are having problems accessing your account, reset your password by clicking the button below:\\n\\n<br/>\\n<br/>\\n<a href=\\\"https://accounts.google.com/RecoverAccount?fpOnly=1&amp;source=ancrppe&amp;Email=inboxapptest@gmail.com\\\" style=\\\"text-align: center; font-size: 11px; font-family: arial, sans-serif; color: white; font-weight: bold; border-color: #3079ed; background-color: #4d90fe; background-image: linear-gradient(top,#4d90fe,#4787ed); text-decoration: none; display:inline-block; height: 27px; padding-left: 8px; padding-right: 8px; line-height: 27px; border-radius: 2px; border-width: 1px;\\\" target=\\\"_blank\\\">\\n<span style=\\\"color: white;\\\">\\n    \\n      Reset password\\n    \\n  </span>\\n</a>\\n<br/>\\n<br/>\\n                \\n                  Sincerely,<br/>\\n                  The Google Accounts team\\n                \\n                </td>\\n<td style=\\\"border-top: none; border-bottom: none; border-left: none; border-right: none;\\\" width=\\\"15\\\">\\n</td>\\n</tr>\\n<tr>\\n<td height=\\\"15\\\" style=\\\"border-top: none; border-bottom: none; border-left: none; border-right: none;\\\">\\n</td>\\n</tr>\\n<tr>\\n<td style=\\\"border-top: none; border-bottom: none; border-left: none; border-right: none;\\\" width=\\\"15\\\"></td>\\n<td style=\\\"font-size: 11px; font-family: arial, sans-serif; color: #777777; border-top: none; border-bottom: none; border-left: none; border-right: none;\\\" width=\\\"568\\\">\\n                \\n                  This email can\'t receive replies. For more information, visit the <a href=\\\"https://support.google.com/accounts/bin/answer.py?answer=2450236\\\" style=\\\"text-decoration: none; color: #4D90FE\\\"><span style=\\\"color: #4D90FE;\\\">Google Accounts Help Center</span></a>.\\n                \\n                </td>\\n<td style=\\\"border-top: none; border-bottom: none; border-left: none; border-right: none;\\\" width=\\\"15\\\"></td>\\n</tr>\\n<tr>\\n<td height=\\\"15\\\" style=\\\"border-top: none; border-bottom: none; border-left: none; border-right: none;\\\">\\n</td>\\n</tr>\\n</table>\\n<table bgcolor=\\\"#f1f1f1\\\" height=\\\"80\\\" style=\\\"text-align: left\\\">\\n<tr valign=\\\"middle\\\">\\n<td style=\\\"font-size: 11px; font-family: arial, sans-serif; color: #777777;\\\">\\n                  \\n                    You received this mandatory email service announcement to update you about important changes to your Google product or account.\\n                  \\n                  <br/>\\n<br/>\\n<div style=\\\"direction: ltr;\\\">\\n                  \\n                    \\u00a9 2013 Google Inc., 1600 Amphitheatre Parkway, Mountain View, CA 94043, USA\\n                  \\n                  </div>\\n</td>\\n</tr>\\n</table>\\n</td>\\n</tr>\\n</table>\\n</body></html>\", \"id\": 10, \"subject\": \"Google Account recovery phone number changed\", \"g_msgid\": 1449471921372979402, \"from_addr\": [[\"\", \"no-reply@accounts.google.com\"]], \"g_thrid\": 1449471921372979402, \"inbox_uid\": null, \"snippet\": \"\\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n            \\n              Inbox App\\n            \\n           \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n            \\n              Hi Inbox,\\n               \\n \\n            \\n\\n\\nThe recove\", \"message_id_header\": \"<MC4rhxPMVYU1ydNeoLDDDA@notifications.google.com>\", \"received_date\": {\"$date\": 1382324143000}, \"size\": 19501, \"type\": \"message\", \"to_addr\": [[\"\", \"inboxapptest@gmail.com\"]], \"mailing_list_headers\": {\"List-Id\": null, \"List-Post\": null, \"List-Owner\": null, \"List-Subscribe\": null, \"List-Unsubscribe\": null, \"List-Archive\": null, \"List-Help\": null}, \"in_reply_to\": null, \"is_draft\": false, \"data_sha256\": \"7836dd4eef7852ea9e9fafae09cc40d18887478d8279d0c2e215c2a7daad3deb\", \"reply_to\": []}',83,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'8ÔøΩ9cÔøΩNÔøΩÔø',NULL,NULL,NULL),('folderitem',29,'insert','{\"thread_id\": 10, \"id\": 29, \"folder_name\": \"archive\"}',84,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'!fÔøΩÔøΩVÔøΩAÔøΩ',NULL,NULL,NULL),('contact',1,'update','{\"score\": 18}',85,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'iÔøΩRÔøΩÔøΩ|NcÔø',NULL,NULL,NULL),('contact',7,'insert','{\"public_id\": \"ekf3dtag2jpkv2ig7w2enzj91\", \"uid\": {\"$uuid\": \"94d616ac3963442a9d05b88d43a94758\"}, \"account_id\": 1, \"source\": \"local\", \"score\": 9, \"provider_name\": \"inbox\", \"email_address\": \"no-reply@accounts.google.com\", \"id\": 7, \"name\": \"\"}',86,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'7vÔøΩ*ÔøΩoNNÔøΩÔ',NULL,NULL,NULL),('part',34,'insert','{\"walk_index\": 1, \"namespace_id\": 1, \"public_id\": \"5ax75yobfwixrdetp1ng44126\", \"misc_keyval\": [[\"Mime-Version\", \"1.0\"], [\"Content-Type\", [\"text/text\", {\"charset\": \"ascii\"}]], [\"Content-Transfer-Encoding\", [\"7bit\", {}]]], \"_content_type_other\": \"text/text\", \"_content_type_common\": null, \"content_id\": null, \"data_sha256\": \"7747fbe457d3e6d5ead68b4d6f39d17cc2b33e24f9fa78ee40dfe8accbad8ae0\", \"id\": 34, \"filename\": null, \"message_id\": 11, \"size\": 31}',87,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'A_ÔøΩPÔøΩ^C<ÔøΩÔ',NULL,NULL,NULL),('folderitem',30,'insert','{\"thread_id\": 11, \"id\": 30, \"folder_name\": \"archive\"}',88,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'\"€ô|bÔøΩHÔøΩÔøΩO',NULL,NULL,NULL),('part',35,'insert','{\"walk_index\": 2, \"namespace_id\": 1, \"public_id\": \"ap322i8toyc00gyrrkrzmxhit\", \"misc_keyval\": [[\"Mime-Version\", \"1.0\"], [\"Content-Type\", [\"text/html\", {\"charset\": \"ascii\"}]], [\"Content-Transfer-Encoding\", [\"7bit\", {}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/html\", \"content_id\": null, \"data_sha256\": \"8c9624e032689b58d2dfa87635f7a2ae2d0b4faa06312065eeacde739c1f2252\", \"id\": 35, \"filename\": null, \"message_id\": 11, \"size\": 61}',89,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'^]ÔøΩÔøΩÔøΩMÔø',NULL,NULL,NULL),('part',33,'insert','{\"walk_index\": 0, \"namespace_id\": 1, \"public_id\": \"6qe3ajoabbndu00y33a97x987\", \"_content_type_other\": null, \"_content_type_common\": null, \"data_sha256\": \"21ddd725936b604c5b970431f6f44c3887797938c8ba98525bb2098c128aed81\", \"id\": 33, \"message_id\": 11, \"size\": 891}',90,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ&ÔøΩÔøΩoH\ZÔø',NULL,NULL,NULL),('message',11,'insert','{\"public_id\": \"djb98ezfhbmjhd62qhqgj7web\", \"sender_addr\": [], \"thread_id\": 11, \"bcc_addr\": [], \"cc_addr\": [[\"\", \"ben.bitdiddle1861@gmail.com\"]], \"references\": \"\", \"sanitized_body\": \"<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>\", \"id\": 11, \"subject\": \"Wakeup78fcb997159345c9b160573e1887264a\", \"g_msgid\": 1466856002099058157, \"from_addr\": [[\"Inbox App\", \"inboxapptest@gmail.com\"]], \"g_thrid\": 1466856002099058157, \"inbox_uid\": \"c64be65384804950972d7cb34cd33c69\", \"snippet\": \"Sea, birds, yoga and sand.\", \"message_id_header\": \"<5361906e.c3ef320a.62fb.064c@mx.google.com>\", \"received_date\": {\"$date\": 1398902894000}, \"size\": 1238, \"type\": \"message\", \"to_addr\": [[\"\\u2605The red-haired mermaid\\u2605\", \"inboxapptest@gmail.com\"]], \"mailing_list_headers\": {\"List-Id\": null, \"List-Post\": null, \"List-Owner\": null, \"List-Subscribe\": null, \"List-Unsubscribe\": null, \"List-Archive\": null, \"List-Help\": null}, \"in_reply_to\": null, \"is_draft\": false, \"data_sha256\": \"aa2f127af89b74364ae781becd35704c48f690a3df0abd90e543eafc2ef4d590\", \"reply_to\": []}',91,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩtXÔøΩÔøΩFÔ',NULL,NULL,NULL),('contact',1,'update','{\"score\": 19}',92,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'◊ÇÔøΩkÔøΩÔøΩLÔøΩ',NULL,NULL,NULL),('part',38,'insert','{\"walk_index\": 2, \"namespace_id\": 1, \"public_id\": \"aytpnjos6jd1bjjhppk3l3ifv\", \"misc_keyval\": [[\"Mime-Version\", \"1.0\"], [\"Content-Type\", [\"text/html\", {\"charset\": \"ascii\"}]], [\"Content-Transfer-Encoding\", [\"7bit\", {}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/html\", \"content_id\": null, \"data_sha256\": \"8c9624e032689b58d2dfa87635f7a2ae2d0b4faa06312065eeacde739c1f2252\", \"id\": 38, \"filename\": null, \"message_id\": 12, \"size\": 61}',93,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩ@«Ñ-*p',NULL,NULL,NULL),('part',36,'insert','{\"walk_index\": 0, \"namespace_id\": 1, \"public_id\": \"1yb2l76yhu9txhtcfkbwd2t3\", \"_content_type_other\": null, \"_content_type_common\": null, \"data_sha256\": \"553b8ce2185f5d66380cf0209f81cb2fa6a3a0e1f59845d8530ed08b38e96a0e\", \"id\": 36, \"message_id\": 12, \"size\": 852}',94,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'lÔøΩi!/B–ÇÔøΩÔø',NULL,NULL,NULL),('folderitem',31,'insert','{\"thread_id\": 12, \"id\": 31, \"folder_name\": \"archive\"}',95,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ ::kDuÔøΩÔøΩ',NULL,NULL,NULL),('message',12,'insert','{\"public_id\": \"k0e9h2pn2my9dc84m3iku8k\", \"sender_addr\": [], \"thread_id\": 12, \"bcc_addr\": [], \"cc_addr\": [[\"\", \"ben.bitdiddle1861@gmail.com\"]], \"references\": \"\", \"sanitized_body\": \"<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>\", \"id\": 12, \"subject\": \"Wakeup1dd3dabe7d9444da8aec3be27a82d030\", \"g_msgid\": 1466855488650356657, \"from_addr\": [[\"Inbox App\", \"inboxapptest@gmail.com\"]], \"g_thrid\": 1466855488650356657, \"inbox_uid\": \"e4f72ba9f22842bab7d41e6c4b877b83\", \"snippet\": \"Sea, birds, yoga and sand.\", \"message_id_header\": \"<53618e85.e14f320a.1f54.21a6@mx.google.com>\", \"received_date\": {\"$date\": 1398902405000}, \"size\": 1199, \"type\": \"message\", \"to_addr\": [[\"\\u2605The red-haired mermaid\\u2605\", \"inboxapptest@gmail.com\"]], \"mailing_list_headers\": {\"List-Id\": null, \"List-Post\": null, \"List-Owner\": null, \"List-Subscribe\": null, \"List-Unsubscribe\": null, \"List-Archive\": null, \"List-Help\": null}, \"in_reply_to\": null, \"is_draft\": false, \"data_sha256\": \"4a07bb7d5d933c811c267c0262525de7c468d735e9b6edb0ee2060b6f24ab330\", \"reply_to\": []}',96,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'oTÔøΩÔøΩ{VHjÔøΩÔ',NULL,NULL,NULL),('part',37,'insert','{\"walk_index\": 1, \"namespace_id\": 1, \"public_id\": \"71pgb9ywiaux79rycl7zd24x4\", \"misc_keyval\": [[\"Mime-Version\", \"1.0\"], [\"Content-Type\", [\"text/text\", {\"charset\": \"ascii\"}]], [\"Content-Transfer-Encoding\", [\"7bit\", {}]]], \"_content_type_other\": \"text/text\", \"_content_type_common\": null, \"content_id\": null, \"data_sha256\": \"7747fbe457d3e6d5ead68b4d6f39d17cc2b33e24f9fa78ee40dfe8accbad8ae0\", \"id\": 37, \"filename\": null, \"message_id\": 12, \"size\": 31}',97,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩuÔøΩÔøΩ2OBÔøΩ',NULL,NULL,NULL),('contact',1,'update','{\"score\": 20}',98,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'‚àæÂá¨HÔøΩÔøΩÔøΩ',NULL,NULL,NULL),('folderitem',32,'insert','{\"thread_id\": 13, \"id\": 32, \"folder_name\": \"archive\"}',99,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩ{ÔøΩ<H«™Ô',NULL,NULL,NULL),('part',40,'insert','{\"walk_index\": 1, \"namespace_id\": 1, \"public_id\": \"eozodoynme9dz7eebc07oekp5\", \"misc_keyval\": [[\"Mime-Version\", \"1.0\"], [\"Content-Type\", [\"text/text\", {\"charset\": \"ascii\"}]], [\"Content-Transfer-Encoding\", [\"7bit\", {}]]], \"_content_type_other\": \"text/text\", \"_content_type_common\": null, \"content_id\": null, \"data_sha256\": \"7747fbe457d3e6d5ead68b4d6f39d17cc2b33e24f9fa78ee40dfe8accbad8ae0\", \"id\": 40, \"filename\": null, \"message_id\": 13, \"size\": 31}',100,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'UÔøΩr2ÔøΩDÔøΩÔø',NULL,NULL,NULL),('part',39,'insert','{\"walk_index\": 0, \"namespace_id\": 1, \"public_id\": \"4t19q2tk6ls09y4bb8cxmc5ti\", \"_content_type_other\": null, \"_content_type_common\": null, \"data_sha256\": \"5f015f0eab6e3adcf8320221b6b0686b73f05a2a3cae54e7367f1d42ba44c734\", \"id\": 39, \"message_id\": 13, \"size\": 853}',101,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ ÔøΩÔøΩIMÔø',NULL,NULL,NULL),('part',41,'insert','{\"walk_index\": 2, \"namespace_id\": 1, \"public_id\": \"cw8hwwytjt17p71ehki9gbvrc\", \"misc_keyval\": [[\"Mime-Version\", \"1.0\"], [\"Content-Type\", [\"text/html\", {\"charset\": \"ascii\"}]], [\"Content-Transfer-Encoding\", [\"7bit\", {}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/html\", \"content_id\": null, \"data_sha256\": \"8c9624e032689b58d2dfa87635f7a2ae2d0b4faa06312065eeacde739c1f2252\", \"id\": 41, \"filename\": null, \"message_id\": 13, \"size\": 61}',102,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'JAÔøΩÔøΩ7ÔøΩDÔøΩ',NULL,NULL,NULL),('message',13,'insert','{\"public_id\": \"97fjigzedwnk3rb8ato4s5b99\", \"sender_addr\": [], \"thread_id\": 13, \"bcc_addr\": [], \"cc_addr\": [[\"\", \"ben.bitdiddle1861@gmail.com\"]], \"references\": \"\", \"sanitized_body\": \"<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>\", \"id\": 13, \"subject\": \"Wakeupe2ea85dc880d421089b7e1fb8cc12c35\", \"g_msgid\": 1466854894292093968, \"from_addr\": [[\"Inbox App\", \"inboxapptest@gmail.com\"]], \"g_thrid\": 1466854894292093968, \"inbox_uid\": \"d1dea076298a4bd09178758433f7542c\", \"snippet\": \"Sea, birds, yoga and sand.\", \"message_id_header\": \"<53618c4e.a983320a.45a5.21a5@mx.google.com>\", \"received_date\": {\"$date\": 1398901838000}, \"size\": 1200, \"type\": \"message\", \"to_addr\": [[\"\\u2605The red-haired mermaid\\u2605\", \"inboxapptest@gmail.com\"]], \"mailing_list_headers\": {\"List-Id\": null, \"List-Post\": null, \"List-Owner\": null, \"List-Subscribe\": null, \"List-Unsubscribe\": null, \"List-Archive\": null, \"List-Help\": null}, \"in_reply_to\": null, \"is_draft\": false, \"data_sha256\": \"91b33ba2f89ca4006d4b5c26d760d4e253bb3f4ed5c87efe964545c2c4ca0db4\", \"reply_to\": []}',103,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩÔøΩ \0ÔøΩJB',NULL,NULL,NULL),('contact',1,'update','{\"score\": 21}',104,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,')ÔøΩ(◊≤ZH“∂`Ôø',NULL,NULL,NULL),('contact',2,'update','{\"score\": 10}',105,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'/wÔøΩÔøΩ›£OÔøΩÔø',NULL,NULL,NULL),('part',44,'insert','{\"walk_index\": 2, \"namespace_id\": 1, \"public_id\": \"7r5mj5l3w82fggryzl7y9f0a0\", \"misc_keyval\": [[\"Mime-Version\", \"1.0\"], [\"Content-Type\", [\"text/html\", {\"charset\": \"ascii\"}]], [\"Content-Transfer-Encoding\", [\"7bit\", {}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/html\", \"content_id\": null, \"data_sha256\": \"8c9624e032689b58d2dfa87635f7a2ae2d0b4faa06312065eeacde739c1f2252\", \"id\": 44, \"filename\": null, \"message_id\": 14, \"size\": 61}',106,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'dÔøΩ25ÔøΩ%IÔøΩÔø',NULL,NULL,NULL),('part',43,'insert','{\"walk_index\": 1, \"namespace_id\": 1, \"public_id\": \"b3l94s1lk9xqdciacziws43k\", \"misc_keyval\": [[\"Mime-Version\", \"1.0\"], [\"Content-Type\", [\"text/text\", {\"charset\": \"ascii\"}]], [\"Content-Transfer-Encoding\", [\"7bit\", {}]]], \"_content_type_other\": \"text/text\", \"_content_type_common\": null, \"content_id\": null, \"data_sha256\": \"7747fbe457d3e6d5ead68b4d6f39d17cc2b33e24f9fa78ee40dfe8accbad8ae0\", \"id\": 43, \"filename\": null, \"message_id\": 14, \"size\": 31}',107,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩÔøΩMÔøΩ&LÔ',NULL,NULL,NULL),('folderitem',33,'insert','{\"thread_id\": 14, \"id\": 33, \"folder_name\": \"archive\"}',108,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩÔøΩÔøΩÔøΩ',NULL,NULL,NULL),('message',14,'insert','{\"public_id\": \"dcgxhwejsfkijv9nlfi25ad9f\", \"sender_addr\": [], \"thread_id\": 14, \"bcc_addr\": [], \"cc_addr\": [[\"\", \"ben.bitdiddle1861@gmail.com\"]], \"references\": \"\", \"sanitized_body\": \"<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>\", \"id\": 14, \"subject\": \"Wakeup735d8864f6124797a10e94ec5de6be13\", \"g_msgid\": 1466761634398434761, \"from_addr\": [[\"Inbox App\", \"inboxapptest@gmail.com\"]], \"g_thrid\": 1466761634398434761, \"inbox_uid\": \"5bf16c2bc9684717a9b77b73cbe9ba45\", \"snippet\": \"Sea, birds, yoga and sand.\", \"message_id_header\": \"<536030e2.640e430a.04ce.ffff8de9@mx.google.com>\", \"received_date\": {\"$date\": 1398812898000}, \"size\": 1205, \"type\": \"message\", \"to_addr\": [[\"\\u2605The red-haired mermaid\\u2605\", \"inboxapptest@gmail.com\"]], \"mailing_list_headers\": {\"List-Id\": null, \"List-Post\": null, \"List-Owner\": null, \"List-Subscribe\": null, \"List-Unsubscribe\": null, \"List-Archive\": null, \"List-Help\": null}, \"in_reply_to\": null, \"is_draft\": false, \"data_sha256\": \"73b93d369f20843a12a81daf72788b1b7fbe703c4abd289f69d1e41f212833a0\", \"reply_to\": []}',109,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ@Q*ÔøΩBÔøΩf',NULL,NULL,NULL),('part',42,'insert','{\"walk_index\": 0, \"namespace_id\": 1, \"public_id\": \"b10systeyyaxcelzv23ngeme8\", \"_content_type_other\": null, \"_content_type_common\": null, \"data_sha256\": \"0b940bea3d7f6e2523605b3e5e91f3d93aa38d780d6ba49f6fd3664ee3b0eaad\", \"id\": 42, \"message_id\": 14, \"size\": 858}',110,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'e5ÔøΩÔøΩcÔøΩEwÔø',NULL,NULL,NULL),('contact',1,'update','{\"score\": 22}',111,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩÔøΩiÔøΩ|E›',NULL,NULL,NULL),('part',46,'insert','{\"walk_index\": 1, \"namespace_id\": 1, \"public_id\": \"cwa3z3ei2il150ayylmz8bld6\", \"misc_keyval\": [[\"Mime-Version\", \"1.0\"], [\"Content-Type\", [\"text/text\", {\"charset\": \"ascii\"}]], [\"Content-Transfer-Encoding\", [\"7bit\", {}]]], \"_content_type_other\": \"text/text\", \"_content_type_common\": null, \"content_id\": null, \"data_sha256\": \"7747fbe457d3e6d5ead68b4d6f39d17cc2b33e24f9fa78ee40dfe8accbad8ae0\", \"id\": 46, \"filename\": null, \"message_id\": 15, \"size\": 31}',112,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩÔøΩMfMKWÔø',NULL,NULL,NULL),('part',45,'insert','{\"walk_index\": 0, \"namespace_id\": 1, \"public_id\": \"71jjzbbu3srbwdmltebcbb3xt\", \"_content_type_other\": null, \"_content_type_common\": null, \"data_sha256\": \"42cefe658856c48397713f475e04af3059fa8c43ee5cc67b7c25ff822f6fdd1c\", \"id\": 45, \"message_id\": 15, \"size\": 895}',113,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ2ÔøΩÔøΩÔøΩgA2',NULL,NULL,NULL),('folderitem',34,'insert','{\"thread_id\": 15, \"id\": 34, \"folder_name\": \"archive\"}',114,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'8SÔøΩÔøΩlC;ÔøΩR',NULL,NULL,NULL),('message',15,'insert','{\"public_id\": \"7sk0a64w7d6j1yad31jd8hzia\", \"sender_addr\": [], \"thread_id\": 15, \"bcc_addr\": [], \"cc_addr\": [[\"\", \"ben.bitdiddle1861@gmail.com\"]], \"references\": \"\", \"sanitized_body\": \"<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>\", \"id\": 15, \"subject\": \"Wakeup2eba715ecd044a55ae4e12f604a8dc96\", \"g_msgid\": 1466761259745473801, \"from_addr\": [[\"Inbox App\", \"inboxapptest@gmail.com\"]], \"g_thrid\": 1466761259745473801, \"inbox_uid\": \"7e7d36a5b6f54af1af551a55b48d1735\", \"snippet\": \"Sea, birds, yoga and sand.\", \"message_id_header\": \"<53602f7d.a6a3420a.73de.6c0b@mx.google.com>\", \"received_date\": {\"$date\": 1398812541000}, \"size\": 1242, \"type\": \"message\", \"to_addr\": [[\"\\u2605The red-haired mermaid\\u2605\", \"inboxapptest@gmail.com\"]], \"mailing_list_headers\": {\"List-Id\": null, \"List-Post\": null, \"List-Owner\": null, \"List-Subscribe\": null, \"List-Unsubscribe\": null, \"List-Archive\": null, \"List-Help\": null}, \"in_reply_to\": null, \"is_draft\": false, \"data_sha256\": \"b13ddac39e20275606cf2f651e269f22f850ac18dce43cf18de982ed3ac20e4f\", \"reply_to\": []}',115,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'›ªÔøΩ1«óDCÔøΩÔøΩ',NULL,NULL,NULL),('part',47,'insert','{\"walk_index\": 2, \"namespace_id\": 1, \"public_id\": \"8rbi9qhj6oqghodwc3gwrwntc\", \"misc_keyval\": [[\"Mime-Version\", \"1.0\"], [\"Content-Type\", [\"text/html\", {\"charset\": \"ascii\"}]], [\"Content-Transfer-Encoding\", [\"7bit\", {}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/html\", \"content_id\": null, \"data_sha256\": \"8c9624e032689b58d2dfa87635f7a2ae2d0b4faa06312065eeacde739c1f2252\", \"id\": 47, \"filename\": null, \"message_id\": 15, \"size\": 61}',116,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩÔøΩÔøΩÔøΩ\'',NULL,NULL,NULL),('contact',1,'update','{\"score\": 23}',117,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ>‹ΩÔøΩÔøΩLÔøΩ',NULL,NULL,NULL),('part',48,'insert','{\"walk_index\": 0, \"namespace_id\": 1, \"public_id\": \"4jwrhu8sh8svr5ixbn5meooup\", \"_content_type_other\": null, \"_content_type_common\": null, \"data_sha256\": \"3a50e724e41242746339a2ad4accd821dca20a73844848c54556d5fc13e58a31\", \"id\": 48, \"message_id\": 16, \"size\": 3092}',118,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'GÔøΩÔøΩÔøΩ3LBÔø',NULL,NULL,NULL),('folderitem',35,'insert','{\"thread_id\": 16, \"id\": 35, \"folder_name\": \"important\"}',119,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩÔøΩQÔøΩBÔøΩIÔ',NULL,NULL,NULL),('part',49,'insert','{\"walk_index\": 1, \"namespace_id\": 1, \"public_id\": \"5lzeffp6m3yh5kmaa1h9cvncu\", \"misc_keyval\": [[\"Content-Type\", [\"text/plain\", {\"charset\": \"UTF-8\"}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/plain\", \"content_id\": null, \"data_sha256\": \"d30c644879e3b7b618dd03d593e67a9b6ff80615e4aea01b06b992dbed47008a\", \"id\": 49, \"filename\": null, \"message_id\": 16, \"size\": 2722}',120,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ*ÔøΩÔøΩ /J€≥Ô',NULL,NULL,NULL),('message',16,'insert','{\"public_id\": \"b07gpwg599b3q2p6ms71z0oeo\", \"sender_addr\": [], \"thread_id\": 16, \"bcc_addr\": [], \"cc_addr\": [], \"references\": \"<CA+ADUwxeXG8+=Mya+T1Qb_RYS23w6=_EZgssm3GgW6SkhXPxGQ@mail.gmail.com>\\t<F7C679E5-09F7-4F17-B1CA-A67A6B207650@gmail.com>\\t<CAPGJ9TSw5oHjhDNGNa3zs4GQ1WC=bCJ8UTdF12NFqgSdYib9FA@mail.gmail.com>\\t<CAPGJ9TRPNG7pS0JTEZog1A+usobFsH3S5nE0EbPbqtwBW3dKKw@mail.gmail.com>\\t<CA+ADUwytg_oZ6B2HfW=v=Vy39G1t1vT17UpjUTaYJuqr8FYR6w@mail.gmail.com>\\t<CALEp7UFOAXWGgMUW9_GVmJfd1xQSfmXHoGs3rajEd6wZwra1Qw@mail.gmail.com>\\t<CA+ADUwwh7gmTDfzVObOkcm0d=5j9mMZt-NxswDqXv9VnpYg_Lg@mail.gmail.com>\\t<CAMpoCYqjMdo=dVvQMZZE5BhZMb2sZkznQnc=7K6kZ_M6NCg+EQ@mail.gmail.com>\\t<CAPGJ9TQi7Rqxr+HmjASJJ0o2OMgFBG5z-mguUQuy8su1fakLiQ@mail.gmail.com>\\t<CA+ADUwzEgH6GC=ji5FT0m+i1XSxu0uamwrqAwGMAZhg-qWvL2g@mail.gmail.com>\\t<CAPGJ9TQkb923ZKeVxqfqB=JeLnhE9-MOAigRrHo-PZCtueZ-Tg@mail.gmail.com>\\t<3A2441BA-C669-4533-A67A-5CE841A82B54@gmail.com>\\t<CALEp7UFN3t=rzzZ_in=3LvAypVN=S9hi_RQkpKwc1kc13ymYTw@mail.gmail.com>\\t<CALRhdLLxFd1L5D+7RoUKVqq0G62cLJezYmMZaST2eiB7kQDCPw@mail.gmail.com>\\t<CAPGJ9TQe4TyhwmS3vbu1hkZgDkNzsb4O2F1OYvvhMxO3v61Ehg@mail.gmail.com>\\t<2D4C6F7D-59F9-4B12-8BEF-3C60556AEC7E@gmail.com>\", \"sanitized_body\": \"<html><body><div dir=\\\"ltr\\\"><br/><br/><br/></div></body></html>\", \"id\": 16, \"subject\": \"Golden Gate Park next Sat\", \"g_msgid\": 1466255156975764289, \"from_addr\": [[\"kavya joshi\", \"kavya719@gmail.com\"]], \"g_thrid\": 1466255156975764289, \"inbox_uid\": null, \"snippet\": \"\", \"message_id_header\": \"<CAMpoCYqq6BmoRW+MouXOwDxiA=DO20b=sG4e2agmr04Bt8Wg_g@mail.gmail.com>\", \"received_date\": {\"$date\": 1398329884000}, \"size\": 13142, \"type\": \"message\", \"to_addr\": [[\"\", \"inboxapptest@gmail.com\"]], \"mailing_list_headers\": {\"List-Id\": null, \"List-Post\": null, \"List-Owner\": null, \"List-Subscribe\": null, \"List-Unsubscribe\": null, \"List-Archive\": null, \"List-Help\": null}, \"in_reply_to\": \"<2D4C6F7D-59F9-4B12-8BEF-3C60556AEC7E@gmail.com>\", \"is_draft\": false, \"data_sha256\": \"a5993aef718c4ce3ffd93f0a3cf3a4e54f93278bcb5873a533de3882c383e706\", \"reply_to\": []}',121,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'-WÔøΩajdBRÔøΩ[[',NULL,NULL,NULL),('part',50,'insert','{\"walk_index\": 2, \"namespace_id\": 1, \"public_id\": \"7mv2uy2nxtvnl7vsh6eds5zjw\", \"misc_keyval\": [[\"Content-Type\", [\"text/html\", {\"charset\": \"UTF-8\"}]], [\"Content-Transfer-Encoding\", [\"quoted-printable\", {}]]], \"_content_type_other\": null, \"_content_type_common\": \"text/html\", \"content_id\": null, \"data_sha256\": \"37a1732d9a602ad020d4bf3c878571d8c19eb968ca61a382a4d2d3fb5e8ef896\", \"id\": 50, \"filename\": null, \"message_id\": 16, \"size\": 6605}',122,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ[ÔøΩÔøΩÔøΩM.',NULL,NULL,NULL),('folderitem',36,'insert','{\"thread_id\": 16, \"id\": 36, \"folder_name\": \"archive\"}',123,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'◊©ÔøΩEÔøΩ\"CÔøΩÔø',NULL,NULL,NULL),('contact',1,'update','{\"score\": 24}',124,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'l\\-ÔøΩ0LMÔøΩÔøΩ',NULL,NULL,NULL),('contact',8,'insert','{\"public_id\": \"5rn57m6b3rp2te4qd5qgh4nk3\", \"uid\": {\"$uuid\": \"47c6565a2c8e49a5a32c9a7aff921248\"}, \"account_id\": 1, \"source\": \"local\", \"score\": 9, \"provider_name\": \"inbox\", \"email_address\": \"kavya719@gmail.com\", \"id\": 8, \"name\": \"kavya joshi\"}',125,1,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL,'ÔøΩ\r7OMNeÔøΩÔøΩ',NULL,NULL,NULL),('tag',18,'insert','{\"namespace_id\": 1, \"public_id\": \"attachment\", \"name\": \"attachment\", \"created_at\": {\"$date\": 1408741493966}, \"updated_at\": {\"$date\": 1408741493966}, \"id\": 18}',126,1,'2014-08-22 21:04:54','2014-08-22 21:04:54',NULL,'R◊„P\'M›è`Ù|∞XÖ','attachment','{\"object\": \"tag\", \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"id\": \"attachment\", \"name\": \"attachment\"}',NULL),('imapthread',10,'update','{\"tagitems\": {\"deleted\": [], \"added\": [{\"tag_id\": 18}]}}',127,1,'2014-08-22 21:04:54','2014-08-22 21:04:54',NULL,'‚¬™∞xtE„ÅGÀ:ß‡]','nzih7tn8yfq1179oqtd6bp0w','{\"object\": \"thread\", \"drafts\": [], \"tags\": [{\"name\": \"inbox\", \"id\": \"inbox\"}, {\"name\": \"all\", \"id\": \"all\"}, {\"name\": \"attachment\", \"id\": \"attachment\"}], \"messages\": [\"4qd8i8xr4udsq27eh8xnwf7i5\"], \"last_message_timestamp\": {\"$date\": 1382324143000}, \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"snippet\": \"\\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n            \\n              Inbox App\\n            \\n           \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n            \\n              Hi Inbox,\\n               \\n \\n            \\n\\n\\nThe recove\", \"participants\": [{\"name\": \"\", \"email\": \"inboxapptest@gmail.com\"}, {\"name\": \"\", \"email\": \"no-reply@accounts.google.com\"}], \"first_message_timestamp\": {\"$date\": 1382324143000}, \"id\": \"nzih7tn8yfq1179oqtd6bp0w\", \"subject\": \"Google Account recovery phone number changed\"}',NULL),('message',14,'update','{\"references\": [], \"updated_at\": {\"$date\": 1409102009191}}',128,1,'2014-08-27 01:13:29','2014-08-27 01:13:29',NULL,'∆øEëäMJçr≈~s∆Å','e6z27et1cjsjyw7vgb3e29igv','{\"body\": \"<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>\", \"files\": [], \"from\": [{\"name\": \"Inbox App\", \"email\": \"inboxapptest@gmail.com\"}], \"thread\": \"e6z2862swmk4duec0ospucszh\", \"cc\": [{\"name\": \"\", \"email\": \"ben.bitdiddle1861@gmail.com\"}], \"object\": \"message\", \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"bcc\": [], \"snippet\": \"Sea, birds, yoga and sand.\", \"to\": [{\"name\": \"\\u2605The red-haired mermaid\\u2605\", \"email\": \"inboxapptest@gmail.com\"}], \"date\": {\"$date\": 1398812898000}, \"unread\": true, \"id\": \"e6z27et1cjsjyw7vgb3e29igv\", \"subject\": \"Wakeup735d8864f6124797a10e94ec5de6be13\"}','{\"recentdate\": {\"$date\": 1398812898000}, \"filenames\": [], \"subjectdate\": {\"$date\": 1398812898000}}'),('message',11,'update','{\"references\": [], \"updated_at\": {\"$date\": 1409102009190}}',129,1,'2014-08-27 01:13:29','2014-08-27 01:13:29',NULL,'\r¡≠ÛI™£[¶⁄\\lﬁ','djb98ezfq1wnltt3odwtysu7j','{\"body\": \"<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>\", \"files\": [], \"from\": [{\"name\": \"Inbox App\", \"email\": \"inboxapptest@gmail.com\"}], \"thread\": \"cy7v7rs6movw71upe29sw0tf3\", \"cc\": [{\"name\": \"\", \"email\": \"ben.bitdiddle1861@gmail.com\"}], \"object\": \"message\", \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"bcc\": [], \"snippet\": \"Sea, birds, yoga and sand.\", \"to\": [{\"name\": \"\\u2605The red-haired mermaid\\u2605\", \"email\": \"inboxapptest@gmail.com\"}], \"date\": {\"$date\": 1398902894000}, \"unread\": true, \"id\": \"djb98ezfq1wnltt3odwtysu7j\", \"subject\": \"Wakeup78fcb997159345c9b160573e1887264a\"}','{\"recentdate\": {\"$date\": 1398902894000}, \"filenames\": [], \"subjectdate\": {\"$date\": 1398902894000}}'),('message',7,'update','{\"references\": [], \"updated_at\": {\"$date\": 1409102009188}}',130,1,'2014-08-27 01:13:29','2014-08-27 01:13:29',NULL,'ì&ø‹Æ+NÓ∂÷à¥ÙA%ˆ','3fqr02v6yjz39aap1mgsiwk3j','{\"body\": \"<html><body><div dir=\\\"ltr\\\">hello</div></body></html>\", \"files\": [], \"from\": [{\"name\": \"Ben Bitdiddle\", \"email\": \"ben.bitdiddle1861@gmail.com\"}], \"thread\": \"e6z2862swr4vyn2474v5ol44f\", \"cc\": [], \"object\": \"message\", \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"bcc\": [], \"snippet\": \"hello\", \"to\": [{\"name\": \"\", \"email\": \"inboxapptest@gmail.com\"}], \"date\": {\"$date\": 1396492483000}, \"unread\": true, \"id\": \"3fqr02v6yjz39aap1mgsiwk3j\", \"subject\": \"another idle test\"}','{\"recentdate\": {\"$date\": 1396492483000}, \"filenames\": [], \"subjectdate\": {\"$date\": 1396492483000}}'),('message',1,'update','{\"references\": [], \"updated_at\": {\"$date\": 1409102009184}}',131,1,'2014-08-27 01:13:29','2014-08-27 01:13:29',NULL,'W∞D°ú:@äÅ¢ı© ˆü','1cvu2b1nz6dj1hof5wb8hy1nz','{\"body\": \"<html><body><div dir=\\\"ltr\\\">iuhasdklfhasdf</div></body></html>\", \"files\": [], \"from\": [{\"name\": \"Ben Bitdiddle\", \"email\": \"ben.bitdiddle1861@gmail.com\"}], \"thread\": \"e6z280wlia8o99mce9j00r4jh\", \"cc\": [], \"object\": \"message\", \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"bcc\": [], \"snippet\": \"iuhasdklfhasdf\", \"to\": [{\"name\": \"\", \"email\": \"inboxapptest@gmail.com\"}], \"date\": {\"$date\": 1396491582000}, \"unread\": true, \"id\": \"1cvu2b1nz6dj1hof5wb8hy1nz\", \"subject\": \"asiuhdakhsdf\"}','{\"recentdate\": {\"$date\": 1396491582000}, \"filenames\": [], \"subjectdate\": {\"$date\": 1396491582000}}'),('message',2,'update','{\"references\": [\"<1286bda0-97a1-47c4-be2d-93b2640f2435@googlegroups.com>\"], \"updated_at\": {\"$date\": 1409102009185}}',132,1,'2014-08-27 01:13:29','2014-08-27 01:13:29',NULL,'@mÏrì—L©°Æô%¨','78pgxboai332pi9p2smo4db73','{\"body\": \"<html><body><div dir=\\\"ltr\\\">I\'d think you\'ll get more help if you can reproduce the issue with smaller code and paste it to Go Playground.<div class=\\\"gmail_extra\\\"></div></div>\\n<p></p>\\n\\n-- <br/>\\nYou received this message because you are subscribed to the Google Groups \\\"golang-nuts\\\" group.<br/>\\nTo unsubscribe from this group and stop receiving emails from it, send an email to <a href=\\\"mailto:golang-nuts+unsubscribe@googlegroups.com\\\">golang-nuts+unsubscribe@googlegroups.com</a>.<br/>\\nFor more options, visit <a href=\\\"https://groups.google.com/d/optout\\\">https://groups.google.com/d/optout</a>.<br/></body></html>\", \"files\": [], \"from\": [{\"name\": \"\'Rui Ueyama\' via golang-nuts\", \"email\": \"golang-nuts@googlegroups.com\"}], \"thread\": \"e6z2862swmdmyqmegz4hvzm5r\", \"cc\": [{\"name\": \"golang-nuts\", \"email\": \"golang-nuts@googlegroups.com\"}], \"object\": \"message\", \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"bcc\": [], \"snippet\": \"I\'d think you\'ll get more help if you can reproduce the issue with smaller code and paste it to Go Playground. \\n \\n\\n--  \\nYou received this message because you are subscribed to the Google Grou\", \"to\": [{\"name\": \"Paul Tiseo\", \"email\": \"paulxtiseo@gmail.com\"}], \"date\": {\"$date\": 1399076765000}, \"unread\": false, \"id\": \"78pgxboai332pi9p2smo4db73\", \"subject\": \"[go-nuts] Runtime Panic On Method Call\"}','{\"recentdate\": {\"$date\": 1399076765000}, \"filenames\": [], \"subjectdate\": {\"$date\": 1399076765000}}'),('message',8,'update','{\"references\": [], \"updated_at\": {\"$date\": 1409102009188}}',133,1,'2014-08-27 01:13:29','2014-08-27 01:13:29',NULL,'Vr√èöBÊÆ˝(ê≈Ù[%','1oiw07gvq5unsxcu3g0gxyrb1','{\"body\": \"<html><body><div dir=\\\"ltr\\\">aoiulhksjndf</div></body></html>\", \"files\": [], \"from\": [{\"name\": \"Ben Bitdiddle\", \"email\": \"ben.bitdiddle1861@gmail.com\"}], \"thread\": \"e6z278ilex4im8g1mfr0iqfel\", \"cc\": [], \"object\": \"message\", \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"bcc\": [], \"snippet\": \"aoiulhksjndf\", \"to\": [{\"name\": \"\", \"email\": \"inboxapptest@gmail.com\"}], \"date\": {\"$date\": 1396493754000}, \"unread\": false, \"id\": \"1oiw07gvq5unsxcu3g0gxyrb1\", \"subject\": \"ohaiulskjndf\"}','{\"recentdate\": {\"$date\": 1396493754000}, \"filenames\": [], \"subjectdate\": {\"$date\": 1396493754000}}'),('message',13,'update','{\"references\": [], \"updated_at\": {\"$date\": 1409102009191}}',134,1,'2014-08-27 01:13:29','2014-08-27 01:13:29',NULL,'49„AE.Ñ9Yñ…õ>','e6z2862swr4vyn2474w1fq7zj','{\"body\": \"<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>\", \"files\": [], \"from\": [{\"name\": \"Inbox App\", \"email\": \"inboxapptest@gmail.com\"}], \"thread\": \"3g25pgybmvxicnhxwa5regm3z\", \"cc\": [{\"name\": \"\", \"email\": \"ben.bitdiddle1861@gmail.com\"}], \"object\": \"message\", \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"bcc\": [], \"snippet\": \"Sea, birds, yoga and sand.\", \"to\": [{\"name\": \"\\u2605The red-haired mermaid\\u2605\", \"email\": \"inboxapptest@gmail.com\"}], \"date\": {\"$date\": 1398901838000}, \"unread\": true, \"id\": \"e6z2862swr4vyn2474w1fq7zj\", \"subject\": \"Wakeupe2ea85dc880d421089b7e1fb8cc12c35\"}','{\"recentdate\": {\"$date\": 1398901838000}, \"filenames\": [], \"subjectdate\": {\"$date\": 1398901838000}}'),('message',6,'update','{\"references\": [], \"updated_at\": {\"$date\": 1409102009187}}',135,1,'2014-08-27 01:13:29','2014-08-27 01:13:29',NULL,'Ø¯È7ïF5ÅˇB~¢£X','e6z2862swr4vymnno8at7fni5','{\"body\": \"<html><body><div dir=\\\"ltr\\\">idle test 123</div></body></html>\", \"files\": [], \"from\": [{\"name\": \"Ben Bitdiddle\", \"email\": \"ben.bitdiddle1861@gmail.com\"}], \"thread\": \"5dt84wdt03lpbghrzuen65f5b\", \"cc\": [], \"object\": \"message\", \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"bcc\": [], \"snippet\": \"idle test 123\", \"to\": [{\"name\": \"\", \"email\": \"inboxapptest@gmail.com\"}], \"date\": {\"$date\": 1396494648000}, \"unread\": false, \"id\": \"e6z2862swr4vymnno8at7fni5\", \"subject\": \"idle test 123\"}','{\"recentdate\": {\"$date\": 1396494648000}, \"filenames\": [], \"subjectdate\": {\"$date\": 1396494648000}}'),('message',12,'update','{\"references\": [], \"updated_at\": {\"$date\": 1409102009190}}',136,1,'2014-08-27 01:13:29','2014-08-27 01:13:29',NULL,'\0Ë2ËåIò{Œ‚¶æ™›','k27yfxslwt6fuur62kyi5rx','{\"body\": \"<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>\", \"files\": [], \"from\": [{\"name\": \"Inbox App\", \"email\": \"inboxapptest@gmail.com\"}], \"thread\": \"6i514g9vvun0i615dehnyp5v3\", \"cc\": [{\"name\": \"\", \"email\": \"ben.bitdiddle1861@gmail.com\"}], \"object\": \"message\", \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"bcc\": [], \"snippet\": \"Sea, birds, yoga and sand.\", \"to\": [{\"name\": \"\\u2605The red-haired mermaid\\u2605\", \"email\": \"inboxapptest@gmail.com\"}], \"date\": {\"$date\": 1398902405000}, \"unread\": true, \"id\": \"k27yfxslwt6fuur62kyi5rx\", \"subject\": \"Wakeup1dd3dabe7d9444da8aec3be27a82d030\"}','{\"recentdate\": {\"$date\": 1398902405000}, \"filenames\": [], \"subjectdate\": {\"$date\": 1398902405000}}'),('message',5,'update','{\"references\": [], \"updated_at\": {\"$date\": 1409102009187}}',137,1,'2014-08-27 01:13:29','2014-08-27 01:13:29',NULL,'kˇLê2ÅBÕÖ0qè˝+=ì','3ueca9iuk49bxno49wnhobokt','{\"body\": \"<html><body><div dir=\\\"ltr\\\">idle trigger</div></body></html>\", \"files\": [], \"from\": [{\"name\": \"Ben Bitdiddle\", \"email\": \"ben.bitdiddle1861@gmail.com\"}], \"thread\": \"e6z2862swms5n0ll4z8esdxod\", \"cc\": [], \"object\": \"message\", \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"bcc\": [], \"snippet\": \"idle trigger\", \"to\": [{\"name\": \"\", \"email\": \"inboxapptest@gmail.com\"}], \"date\": {\"$date\": 1396492114000}, \"unread\": true, \"id\": \"3ueca9iuk49bxno49wnhobokt\", \"subject\": \"idle trigger\"}','{\"recentdate\": {\"$date\": 1396492114000}, \"filenames\": [], \"subjectdate\": {\"$date\": 1396492114000}}'),('message',15,'update','{\"references\": [], \"updated_at\": {\"$date\": 1409102009192}}',138,1,'2014-08-27 01:13:29','2014-08-27 01:13:29',NULL,'íGGgπ\'B3Ö=/ò<û','e6z2862swm3jr65avpcsdihr2','{\"body\": \"<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>\", \"files\": [], \"from\": [{\"name\": \"Inbox App\", \"email\": \"inboxapptest@gmail.com\"}], \"thread\": \"3ouuxafvl37y3nzjpj4udr6pp\", \"cc\": [{\"name\": \"\", \"email\": \"ben.bitdiddle1861@gmail.com\"}], \"object\": \"message\", \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"bcc\": [], \"snippet\": \"Sea, birds, yoga and sand.\", \"to\": [{\"name\": \"\\u2605The red-haired mermaid\\u2605\", \"email\": \"inboxapptest@gmail.com\"}], \"date\": {\"$date\": 1398812541000}, \"unread\": true, \"id\": \"e6z2862swm3jr65avpcsdihr2\", \"subject\": \"Wakeup2eba715ecd044a55ae4e12f604a8dc96\"}','{\"recentdate\": {\"$date\": 1398812541000}, \"filenames\": [], \"subjectdate\": {\"$date\": 1398812541000}}'),('message',9,'update','{\"references\": [], \"updated_at\": {\"$date\": 1409102009189}}',139,1,'2014-08-27 01:13:29','2014-08-27 01:13:29',NULL,'8%Q&›3B@ΩŒ!¨Îä\"','m7gcpzvkmn2zwoktw3xl3dfj','{\"body\": \"<html><body><div dir=\\\"ltr\\\">a8ogysuidfaysogudhkbjfasdf<div><br/></div></div></body></html>\", \"files\": [], \"from\": [{\"name\": \"Ben Bitdiddle\", \"email\": \"ben.bitdiddle1861@gmail.com\"}], \"thread\": \"63net1wzz61z6iu9b9sxgomqy\", \"cc\": [], \"object\": \"message\", \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"bcc\": [], \"snippet\": \"a8ogysuidfaysogudhkbjfasdf\", \"to\": [{\"name\": \"\", \"email\": \"inboxapptest@gmail.com\"}], \"date\": {\"$date\": 1396493160000}, \"unread\": true, \"id\": \"m7gcpzvkmn2zwoktw3xl3dfj\", \"subject\": \"guaysdhbjkf\"}','{\"recentdate\": {\"$date\": 1396493160000}, \"filenames\": [], \"subjectdate\": {\"$date\": 1396493160000}}'),('message',10,'update','{\"references\": [], \"updated_at\": {\"$date\": 1409102009189}}',140,1,'2014-08-27 01:13:29','2014-08-27 01:13:29',NULL,'√ü‘nŸ¨DÃò§Ü≤G›Yf','4qd8i8xr4udsq27eh8xnwf7i5','{\"body\": \"<html lang=\\\"en\\\"><body style=\\\"margin:0; padding: 0;\\\">\\n<table align=\\\"center\\\" bgcolor=\\\"#f1f1f1\\\" border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" height=\\\"100%\\\" style=\\\"border-collapse: collapse\\\" width=\\\"100%\\\">\\n<tr align=\\\"center\\\">\\n<td valign=\\\"top\\\">\\n<table bgcolor=\\\"#f1f1f1\\\" border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" height=\\\"60\\\" style=\\\"border-collapse: collapse\\\">\\n<tr height=\\\"40\\\" valign=\\\"middle\\\">\\n<td width=\\\"9\\\"></td>\\n<td valign=\\\"middle\\\" width=\\\"217\\\">\\n<img alt=\\\"Google Accounts\\\" border=\\\"0\\\" height=\\\"40\\\" src=\\\"cid:google\\\" style=\\\"display: block;\\\"/>\\n</td>\\n<td style=\\\"font-size: 13px; font-family: arial, sans-serif; color: #777777; text-align: right\\\" width=\\\"327\\\">\\n            \\n              Inbox App\\n            \\n          </td>\\n<td width=\\\"10\\\"></td>\\n<td><img src=\\\"cid:profilephoto\\\"/></td>\\n<td width=\\\"10\\\"></td>\\n</tr>\\n</table>\\n<table bgcolor=\\\"#ffffff\\\" border=\\\"1\\\" bordercolor=\\\"#e5e5e5\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"text-align: left\\\">\\n<tr>\\n<td height=\\\"15\\\" style=\\\"border-top: none; border-bottom: none; border-left: none; border-right: none;\\\">\\n</td>\\n</tr>\\n<tr>\\n<td style=\\\"border-top: none; border-bottom: none; border-left: none; border-right: none;\\\" width=\\\"15\\\">\\n</td>\\n<td style=\\\"font-size: 83%; border-top: none; border-bottom: none; border-left: none; border-right: none; font-size: 13px; font-family: arial, sans-serif; color: #222222; line-height: 18px\\\" valign=\\\"top\\\" width=\\\"568\\\">\\n            \\n              Hi Inbox,\\n              <br/>\\n<br/>\\n            \\n\\n\\nThe recovery phone number for your Google Account - inboxapptest@gmail.com - was recently changed. If you made this change, you don\'t need to do anything more.\\n\\n<br/>\\n<br/>\\n\\nIf you didn\'t change your recovery phone, someone may have broken into your account. Visit this link for more information: <a href=\\\"https://support.google.com/accounts/bin/answer.py?answer=2450236\\\" style=\\\"text-decoration: none; color: #4D90FE\\\">https://support.google.com/accounts/bin/answer.py?answer=2450236</a>.\\n\\n<br/>\\n<br/>\\n\\nIf you are having problems accessing your account, reset your password by clicking the button below:\\n\\n<br/>\\n<br/>\\n<a href=\\\"https://accounts.google.com/RecoverAccount?fpOnly=1&amp;source=ancrppe&amp;Email=inboxapptest@gmail.com\\\" style=\\\"text-align: center; font-size: 11px; font-family: arial, sans-serif; color: white; font-weight: bold; border-color: #3079ed; background-color: #4d90fe; background-image: linear-gradient(top,#4d90fe,#4787ed); text-decoration: none; display:inline-block; height: 27px; padding-left: 8px; padding-right: 8px; line-height: 27px; border-radius: 2px; border-width: 1px;\\\" target=\\\"_blank\\\">\\n<span style=\\\"color: white;\\\">\\n    \\n      Reset password\\n    \\n  </span>\\n</a>\\n<br/>\\n<br/>\\n                \\n                  Sincerely,<br/>\\n                  The Google Accounts team\\n                \\n                </td>\\n<td style=\\\"border-top: none; border-bottom: none; border-left: none; border-right: none;\\\" width=\\\"15\\\">\\n</td>\\n</tr>\\n<tr>\\n<td height=\\\"15\\\" style=\\\"border-top: none; border-bottom: none; border-left: none; border-right: none;\\\">\\n</td>\\n</tr>\\n<tr>\\n<td style=\\\"border-top: none; border-bottom: none; border-left: none; border-right: none;\\\" width=\\\"15\\\"></td>\\n<td style=\\\"font-size: 11px; font-family: arial, sans-serif; color: #777777; border-top: none; border-bottom: none; border-left: none; border-right: none;\\\" width=\\\"568\\\">\\n                \\n                  This email can\'t receive replies. For more information, visit the <a href=\\\"https://support.google.com/accounts/bin/answer.py?answer=2450236\\\" style=\\\"text-decoration: none; color: #4D90FE\\\"><span style=\\\"color: #4D90FE;\\\">Google Accounts Help Center</span></a>.\\n                \\n                </td>\\n<td style=\\\"border-top: none; border-bottom: none; border-left: none; border-right: none;\\\" width=\\\"15\\\"></td>\\n</tr>\\n<tr>\\n<td height=\\\"15\\\" style=\\\"border-top: none; border-bottom: none; border-left: none; border-right: none;\\\">\\n</td>\\n</tr>\\n</table>\\n<table bgcolor=\\\"#f1f1f1\\\" height=\\\"80\\\" style=\\\"text-align: left\\\">\\n<tr valign=\\\"middle\\\">\\n<td style=\\\"font-size: 11px; font-family: arial, sans-serif; color: #777777;\\\">\\n                  \\n                    You received this mandatory email service announcement to update you about important changes to your Google product or account.\\n                  \\n                  <br/>\\n<br/>\\n<div style=\\\"direction: ltr;\\\">\\n                  \\n                    \\u00a9 2013 Google Inc., 1600 Amphitheatre Parkway, Mountain View, CA 94043, USA\\n                  \\n                  </div>\\n</td>\\n</tr>\\n</table>\\n</td>\\n</tr>\\n</table>\\n</body></html>\", \"files\": [{\"size\": 6321, \"id\": \"2ln36acdr3pnjvn9ds8mq3xrx\", \"content_type\": \"image/png\", \"filename\": \"google.png\"}, {\"size\": 565, \"id\": \"e6z27cxy9h7zgk69sq729xik9\", \"content_type\": \"image/png\", \"filename\": \"profilephoto.png\"}], \"from\": [{\"name\": \"\", \"email\": \"no-reply@accounts.google.com\"}], \"thread\": \"nzih7tn8yfq1179oqtd6bp0w\", \"cc\": [], \"object\": \"message\", \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"bcc\": [], \"snippet\": \"\\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n            \\n              Inbox App\\n            \\n           \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n \\n            \\n              Hi Inbox,\\n               \\n \\n            \\n\\n\\nThe recove\", \"to\": [{\"name\": \"\", \"email\": \"inboxapptest@gmail.com\"}], \"date\": {\"$date\": 1382324143000}, \"unread\": true, \"id\": \"4qd8i8xr4udsq27eh8xnwf7i5\", \"subject\": \"Google Account recovery phone number changed\"}','{\"recentdate\": {\"$date\": 1382324143000}, \"filenames\": [\"google.png\", \"profilephoto.png\"], \"subjectdate\": {\"$date\": 1382324143000}}'),('message',3,'update','{\"references\": [], \"updated_at\": {\"$date\": 1409102009186}}',141,1,'2014-08-27 01:13:29','2014-08-27 01:13:29',NULL,'?-∂ﬂñæ@ËñVÆ√ÈQ“','e6z2862swmt2bg3f5i1i2op8f','{\"body\": \"<html xmlns=\\\"http://www.w3.org/1999/xhtml\\\"><head><meta content=\\\"text/html;charset=utf-8\\\" http-equiv=\\\"content-type\\\"/><title>Tips for using Gmail</title></head><body link=\\\"#1155CC\\\" marginheight=\\\"0\\\" marginwidth=\\\"0\\\" text=\\\"#444444\\\">\\n<table bgcolor=\\\"#f5f5f5\\\" border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse: collapse;\\\" width=\\\"100%\\\">\\n<tr>\\n<td> </td>\\n<td height=\\\"51\\\" width=\\\"64\\\"><img alt=\\\"\\\" height=\\\"51\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-top-left.png\\\" style=\\\"display:block\\\" width=\\\"64\\\"/></td>\\n<td background=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-top-middle.png\\\" bgcolor=\\\"#f5f5f5\\\" height=\\\"51\\\" valign=\\\"bottom\\\" width=\\\"673\\\">\\n</td>\\n<td height=\\\"51\\\" width=\\\"64\\\"><img alt=\\\"\\\" height=\\\"51\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-top-right.png\\\" style=\\\"display:block\\\" width=\\\"68\\\"/></td>\\n<td> </td>\\n</tr>\\n<tr>\\n<td> </td>\\n<td height=\\\"225\\\" width=\\\"64\\\"><img alt=\\\"\\\" height=\\\"225\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-middle-1-left.png\\\" style=\\\"display:block\\\" width=\\\"64\\\"/></td>\\n<td bgcolor=\\\"#ffffff\\\" valign=\\\"top\\\" width=\\\"668\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse: collapse; \\\" width=\\\"100%\\\">\\n<tr>\\n<td colspan=\\\"3\\\"> </td>\\n</tr>\\n<tr>\\n<td align=\\\"center\\\" colspan=\\\"3\\\" height=\\\"50\\\" valign=\\\"bottom\\\"><img alt=\\\"\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/logo.gif\\\" style=\\\"display:block\\\"/></td>\\n</tr>\\n<tr>\\n<td colspan=\\\"3\\\" height=\\\"40\\\"> </td>\\n</tr>\\n<tr>\\n<td> </td>\\n<td width=\\\"450\\\">\\n<b>\\n<font color=\\\"#444444\\\" face=\\\"Arial, sans-serif\\\" size=\\\"-1\\\" style=\\\"line-height: 1.4em\\\">\\n<img alt=\\\"\\\" src=\\\"https://ssl.gstatic.com/accounts/services/mail/msa/gmail_icon_small.png\\\" style=\\\"display:block;float:left;margin-top:4px;margin-right:3px;\\\"/>Hi Inbox\\n                    </font>\\n</b>\\n</td>\\n<td> </td>\\n</tr>\\n<tr>\\n<td height=\\\"40\\\" valign=\\\"top\\\">\\n</td></tr>\\n<tr>\\n<td width=\\\"111\\\"> </td>\\n<td align=\\\"left\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse: collapse;\\\" width=\\\"540\\\">\\n<tr>\\n<td valign=\\\"top\\\"><font color=\\\"#444444\\\" face=\\\"Arial, sans-serif\\\" size=\\\"+2\\\"><span style=\\\"font-family:Open Sans, Arial, sans-serif; font-size: 25px\\\">Tips for using Gmail</span></font></td>\\n</tr>\\n</table>\\n</td>\\n<td width=\\\"111\\\"> </td>\\n</tr>\\n<tr>\\n<td colspan=\\\"3\\\" height=\\\"10\\\"> </td>\\n</tr>\\n</table>\\n</td>\\n<td height=\\\"225\\\" width=\\\"64\\\"><img alt=\\\"\\\" height=\\\"225\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-middle-1-right.png\\\" style=\\\"display:block\\\" width=\\\"64\\\"/></td>\\n<td> </td>\\n</tr>\\n<tr>\\n<td> </td>\\n<td height=\\\"950\\\" width=\\\"64\\\"><img alt=\\\"\\\" height=\\\"950\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-middle-2-left.png\\\" style=\\\"display:block\\\" width=\\\"64\\\"/></td>\\n<td align=\\\"center\\\" bgcolor=\\\"#ffffff\\\" valign=\\\"top\\\" width=\\\"668\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse: collapse;\\\" width=\\\"540\\\">\\n<tr>\\n<td align=\\\"left\\\">\\n<img alt=\\\"\\\" src=\\\"https://ssl.gstatic.com/accounts/services/mail/msa/welcome_hangouts.png\\\" style=\\\"display:block\\\"/>\\n</td>\\n<td width=\\\"15\\\"></td>\\n<td align=\\\"left\\\" valign=\\\"middle\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse:collapse;\\\" width=\\\"400\\\">\\n<tr>\\n<td align=\\\"left\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"+1\\\"><span style=\\\"font-family:Arial, sans-serif; font-size: 20px;\\\">Chat right from your inbox</span></font>\\n</td>\\n</tr>\\n<tr>\\n<td height=\\\"10\\\"></td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\" valign=\\\"top\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"-1\\\" style=\\\"line-height:1.4em\\\">Chat with contacts and start video chats with up to 10 people in <a href=\\\"http://www.google.com/+/learnmore/hangouts/?hl=en\\\" style=\\\"text-decoration:none;\\\">Google+ Hangouts</a>.</font>\\n</td>\\n</tr>\\n</table>\\n</td>\\n</tr>\\n<tr>\\n<td colspan=\\\"3\\\" height=\\\"30\\\"> </td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\">\\n<img alt=\\\"\\\" src=\\\"https://ssl.gstatic.com/accounts/services/mail/msa/welcome_contacts.png\\\" style=\\\"display:block\\\"/>\\n</td>\\n<td width=\\\"15\\\"></td>\\n<td align=\\\"left\\\" valign=\\\"middle\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse:collapse;\\\" width=\\\"400\\\">\\n<tr>\\n<td align=\\\"left\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"+1\\\"><span style=\\\"font-family:Arial, sans-serif; font-size: 20px;\\\">Bring your email into Gmail</span></font>\\n</td>\\n</tr>\\n<tr>\\n<td height=\\\"10\\\"></td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\" valign=\\\"top\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"-1\\\" style=\\\"line-height:1.4em\\\">You can import your email from other webmail to make the transition to Gmail a bit easier. <a href=\\\"https://support.google.com/mail/answer/164640?hl=en\\\" style=\\\"text-decoration:none;\\\">Learn how.</a></font>\\n</td>\\n</tr>\\n</table>\\n</td>\\n</tr>\\n<tr>\\n<td colspan=\\\"3\\\" height=\\\"30\\\"> </td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\">\\n<img alt=\\\"\\\" src=\\\"https://ssl.gstatic.com/mail/welcome/localized/en/welcome_drive.png\\\" style=\\\"display:block\\\"/>\\n</td>\\n<td width=\\\"15\\\"></td>\\n<td align=\\\"left\\\" valign=\\\"middle\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse:collapse;\\\" width=\\\"400\\\">\\n<tr>\\n<td align=\\\"left\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"+1\\\"><span style=\\\"font-family:Arial, sans-serif; font-size: 20px;\\\">Use Google Drive to send large files</span></font>\\n</td>\\n</tr>\\n<tr>\\n<td height=\\\"10\\\"></td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\" valign=\\\"top\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"-1\\\" style=\\\"line-height:1.4em\\\"><a href=\\\"https://support.google.com/mail/answer/2480713?hl=en\\\" style=\\\"text-decoration:none;\\\">Send huge files in Gmail </a>  (up to 10GB) using <a href=\\\"https://drive.google.com/?hl=en\\\" style=\\\"text-decoration:none;\\\">Google Drive</a>. Plus files stored in Drive stay up-to-date automatically so everyone has the most recent version and can access them from anywhere.</font>\\n</td>\\n</tr>\\n</table>\\n</td>\\n</tr>\\n<tr>\\n<td colspan=\\\"3\\\" height=\\\"30\\\"> </td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\">\\n<img alt=\\\"\\\" src=\\\"https://ssl.gstatic.com/accounts/services/mail/msa/welcome_storage.png\\\" style=\\\"display:block\\\"/>\\n</td>\\n<td width=\\\"15\\\"></td>\\n<td align=\\\"left\\\" valign=\\\"middle\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse:collapse;\\\" width=\\\"400\\\">\\n<tr>\\n<td align=\\\"left\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"+1\\\"><span style=\\\"font-family:Arial, sans-serif; font-size: 20px;\\\">Save everything</span></font>\\n</td>\\n</tr>\\n<tr>\\n<td height=\\\"10\\\"></td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\" valign=\\\"top\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"-1\\\" style=\\\"line-height:1.4em\\\">With 10GB of space, you\\u2019ll never need to delete an email. Just keep everything and easily find it later.</font>\\n</td>\\n</tr>\\n</table>\\n</td>\\n</tr>\\n<tr>\\n<td colspan=\\\"3\\\" height=\\\"30\\\"> </td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\">\\n<img alt=\\\"\\\" src=\\\"https://ssl.gstatic.com/mail/welcome/localized/en/welcome_search.png\\\" style=\\\"display:block\\\"/>\\n</td>\\n<td width=\\\"15\\\"></td>\\n<td align=\\\"left\\\" valign=\\\"middle\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse:collapse;\\\" width=\\\"400\\\">\\n<tr>\\n<td align=\\\"left\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"+1\\\"><span style=\\\"font-family:Arial, sans-serif; font-size: 20px;\\\">Find emails fast</span></font>\\n</td>\\n</tr>\\n<tr>\\n<td height=\\\"10\\\"></td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\" valign=\\\"top\\\">\\n<font color=\\\"#444444\\\" face=\\\"Arial,sans-serif\\\" size=\\\"-1\\\" style=\\\"line-height:1.4em\\\">With the power of Google Search right in your inbox, you can quickly find the important emails you need with suggestions based on emails, past searches and contacts.</font>\\n</td>\\n</tr>\\n</table>\\n</td>\\n</tr>\\n<tr>\\n<td colspan=\\\"3\\\" height=\\\"30\\\"> </td>\\n</tr>\\n</table>\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse: collapse; \\\" width=\\\"500\\\">\\n<tr>\\n<td colspan=\\\"2\\\" height=\\\"40\\\"> </td>\\n</tr>\\n<tr>\\n<td rowspan=\\\"2\\\" width=\\\"68\\\"><img alt=\\\"\\\" src=\\\"https://ssl.gstatic.com/accounts/services/mail/msa/gmail_icon_large.png\\\" style=\\\"display:block\\\"/></td>\\n<td align=\\\"left\\\" height=\\\"20\\\" valign=\\\"bottom\\\"><font color=\\\"#444444\\\" face=\\\"Arial, sans-serif\\\" size=\\\"-1\\\">Happy emailing,</font></td>\\n</tr>\\n<tr>\\n<td align=\\\"left\\\" valign=\\\"top\\\"><font color=\\\"#444444\\\" face=\\\"Arial, sans-serif\\\" size=\\\"+2\\\"><span style=\\\"font-family:Open Sans, Arial, sans-serif;\\\">The Gmail Team</span></font></td>\\n</tr>\\n<tr>\\n<td colspan=\\\"2\\\" height=\\\"60\\\"> </td>\\n</tr>\\n</table>\\n</td>\\n<td height=\\\"950\\\" width=\\\"64\\\"><img alt=\\\"\\\" height=\\\"950\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-middle-2-right.png\\\" style=\\\"display:block\\\" width=\\\"64\\\"/></td>\\n<td> </td>\\n</tr>\\n<tr>\\n<td> </td>\\n<td height=\\\"102\\\" width=\\\"64\\\"><img alt=\\\"\\\" height=\\\"102\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-bottom-left.png\\\" style=\\\"display:block\\\" width=\\\"64\\\"/></td>\\n<td background=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-bottom-middle.png\\\" height=\\\"102\\\" valign=\\\"top\\\" width=\\\"673\\\">\\n<table border=\\\"0\\\" cellpadding=\\\"0\\\" cellspacing=\\\"0\\\" style=\\\"border-collapse: collapse; \\\" width=\\\"100%\\\">\\n<tr>\\n<td height=\\\"12\\\"></td>\\n</tr>\\n<tr>\\n<td valign=\\\"bottom\\\">\\n<font color=\\\"#AAAAAA\\\" face=\\\"Arial, sans-serif\\\" size=\\\"-2\\\">\\n                  \\u00a9 2013 Google Inc. 1600 Amphitheatre Parkway, Mountain View, CA 94043\\n                </font>\\n</td>\\n</tr>\\n</table>\\n</td>\\n<td height=\\\"102\\\" width=\\\"64\\\"><img alt=\\\"\\\" height=\\\"102\\\" src=\\\"https://ssl.gstatic.com/drive/announcements/images/framework-bottom-right.png\\\" style=\\\"display:block\\\" width=\\\"68\\\"/></td>\\n<td> </td>\\n</tr>\\n</table>\\n</body></html>\", \"files\": [], \"from\": [{\"name\": \"Gmail Team\", \"email\": \"mail-noreply@google.com\"}], \"thread\": \"e6z26rjrxs2gu8at6gsa8svr1\", \"cc\": [], \"object\": \"message\", \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"bcc\": [], \"snippet\": \"\\n \\n \\n   \\n \\n \\n \\n \\n   \\n \\n \\n   \\n \\n \\n \\n \\n   \\n \\n \\n \\n \\n \\n   \\n \\n \\n   \\n \\n \\n \\n Hi Inbox\\n                     \\n \\n \\n   \\n \\n \\n \\n \\n \\n   \\n \\n \\n \\n Tips for using Gmail \\n \\n \\n \\n   \\n \\n \\n   \\n \\n \\n \\n \\n   \\n \\n \\n   \\n \", \"to\": [{\"name\": \"Inbox App\", \"email\": \"inboxapptest@gmail.com\"}], \"date\": {\"$date\": 1377021748000}, \"unread\": false, \"id\": \"e6z2862swmt2bg3f5i1i2op8f\", \"subject\": \"Tips for using Gmail\"}','{\"recentdate\": {\"$date\": 1377021748000}, \"filenames\": [], \"subjectdate\": {\"$date\": 1377021748000}}'),('message',4,'update','{\"references\": [], \"updated_at\": {\"$date\": 1409102009186}}',142,1,'2014-08-27 01:13:29','2014-08-27 01:13:29',NULL,'¨îˇ†CK∫”ÉK”é','464qbswi15o1woaj127sx4n9b','{\"body\": \"<html><body><div dir=\\\"ltr\\\">hi</div></body></html>\", \"files\": [], \"from\": [{\"name\": \"Christine Spang\", \"email\": \"christine@spang.cc\"}], \"thread\": \"6cc6su9nf3n9lkfts7qhcv2rj\", \"cc\": [], \"object\": \"message\", \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"bcc\": [], \"snippet\": \"hi\", \"to\": [{\"name\": \"\", \"email\": \"inboxapptest@gmail.com\"}], \"date\": {\"$date\": 1395377580000}, \"unread\": true, \"id\": \"464qbswi15o1woaj127sx4n9b\", \"subject\": \"trigger poll\"}','{\"recentdate\": {\"$date\": 1395377580000}, \"filenames\": [], \"subjectdate\": {\"$date\": 1395377580000}}'),('message',16,'update','{\"references\": [\"<CA+ADUwxeXG8+=Mya+T1Qb_RYS23w6=_EZgssm3GgW6SkhXPxGQ@mail.gmail.com>\", \"<F7C679E5-09F7-4F17-B1CA-A67A6B207650@gmail.com>\", \"<CAPGJ9TSw5oHjhDNGNa3zs4GQ1WC=bCJ8UTdF12NFqgSdYib9FA@mail.gmail.com>\", \"<CAPGJ9TRPNG7pS0JTEZog1A+usobFsH3S5nE0EbPbqtwBW3dKKw@mail.gmail.com>\", \"<CA+ADUwytg_oZ6B2HfW=v=Vy39G1t1vT17UpjUTaYJuqr8FYR6w@mail.gmail.com>\", \"<CALEp7UFOAXWGgMUW9_GVmJfd1xQSfmXHoGs3rajEd6wZwra1Qw@mail.gmail.com>\", \"<CA+ADUwwh7gmTDfzVObOkcm0d=5j9mMZt-NxswDqXv9VnpYg_Lg@mail.gmail.com>\", \"<CAMpoCYqjMdo=dVvQMZZE5BhZMb2sZkznQnc=7K6kZ_M6NCg+EQ@mail.gmail.com>\", \"<CAPGJ9TQi7Rqxr+HmjASJJ0o2OMgFBG5z-mguUQuy8su1fakLiQ@mail.gmail.com>\", \"<CA+ADUwzEgH6GC=ji5FT0m+i1XSxu0uamwrqAwGMAZhg-qWvL2g@mail.gmail.com>\", \"<CAPGJ9TQkb923ZKeVxqfqB=JeLnhE9-MOAigRrHo-PZCtueZ-Tg@mail.gmail.com>\", \"<3A2441BA-C669-4533-A67A-5CE841A82B54@gmail.com>\", \"<CALEp7UFN3t=rzzZ_in=3LvAypVN=S9hi_RQkpKwc1kc13ymYTw@mail.gmail.com>\", \"<CALRhdLLxFd1L5D+7RoUKVqq0G62cLJezYmMZaST2eiB7kQDCPw@mail.gmail.com>\", \"<CAPGJ9TQe4TyhwmS3vbu1hkZgDkNzsb4O2F1OYvvhMxO3v61Ehg@mail.gmail.com>\", \"<2D4C6F7D-59F9-4B12-8BEF-3C60556AEC7E@gmail.com>\"], \"updated_at\": {\"$date\": 1409102009192}}',143,1,'2014-08-27 01:13:29','2014-08-27 01:13:29',NULL,'E“èkµ`KÅÅ¸J+w∂ê','e6z2862swr4vymohzh0wfoo8t','{\"body\": \"<html><body><div dir=\\\"ltr\\\"><br/><br/><br/></div></body></html>\", \"files\": [], \"from\": [{\"name\": \"kavya joshi\", \"email\": \"kavya719@gmail.com\"}], \"thread\": \"2f8wqab0xck4pxxust02o620v\", \"cc\": [], \"object\": \"message\", \"namespace\": \"3q4vzllntcsea53vxz4erbnxr\", \"bcc\": [], \"snippet\": \"\", \"to\": [{\"name\": \"\", \"email\": \"inboxapptest@gmail.com\"}], \"date\": {\"$date\": 1398329884000}, \"unread\": false, \"id\": \"e6z2862swr4vymohzh0wfoo8t\", \"subject\": \"Golden Gate Park next Sat\"}','{\"recentdate\": {\"$date\": 1398329884000}, \"filenames\": [], \"subjectdate\": {\"$date\": 1398329884000}}');
/*!40000 ALTER TABLE `transaction` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `uidvalidity`
--

DROP TABLE IF EXISTS `uidvalidity`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `uidvalidity` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `imapaccount_id` int(11) NOT NULL,
  `folder_name` varchar(191) NOT NULL,
  `uid_validity` int(11) NOT NULL,
  `highestmodseq` int(11) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `imapaccount_id` (`imapaccount_id`,`folder_name`),
  KEY `ix_uidvalidity_created_at` (`created_at`),
  KEY `ix_uidvalidity_deleted_at` (`deleted_at`),
  KEY `ix_uidvalidity_updated_at` (`updated_at`),
  CONSTRAINT `uidvalidity_ibfk_1` FOREIGN KEY (`imapaccount_id`) REFERENCES `imapaccount` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `uidvalidity`
--

LOCK TABLES `uidvalidity` WRITE;
/*!40000 ALTER TABLE `uidvalidity` DISABLE KEYS */;
INSERT INTO `uidvalidity` VALUES (1,1,'INBOX',1,106957,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL),(2,1,'[Gmail]/All Mail',11,106957,'2014-05-13 02:19:13','2014-05-13 02:19:13',NULL);
/*!40000 ALTER TABLE `uidvalidity` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `webhook`
--

DROP TABLE IF EXISTS `webhook`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `webhook` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `public_id` binary(16) NOT NULL,
  `namespace_id` int(11) NOT NULL,
  `callback_url` text NOT NULL,
  `failure_notify_url` text,
  `include_body` tinyint(1) NOT NULL,
  `max_retries` int(11) NOT NULL DEFAULT '3',
  `retry_interval` int(11) NOT NULL DEFAULT '60',
  `active` tinyint(1) NOT NULL DEFAULT '1',
  `min_processed_id` int(11) NOT NULL DEFAULT '0',
  `lens_id` int(11) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `namespace_id` (`namespace_id`),
  KEY `ix_webhook_namespace_id` (`namespace_id`),
  KEY `ix_webhook_public_id` (`public_id`),
  KEY `ix_webhook_lens_id` (`lens_id`),
  KEY `ix_webhook_created_at` (`created_at`),
  KEY `ix_webhook_deleted_at` (`deleted_at`),
  KEY `ix_webhook_updated_at` (`updated_at`),
  CONSTRAINT `webhooks_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE,
  CONSTRAINT `webhook_ibfk_1` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `webhook`
--

LOCK TABLES `webhook` WRITE;
/*!40000 ALTER TABLE `webhook` DISABLE KEYS */;
/*!40000 ALTER TABLE `webhook` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2014-08-27 22:31:24
