-- MySQL dump 10.13  Distrib 8.0.31, for Win64 (x86_64)
--
-- Host: localhost    Database: panet1
-- ------------------------------------------------------
-- Server version	8.0.25

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Dumping data for table `documenti_causdocu`
--

LOCK TABLES `documenti_causdocu` WRITE;
/*!40000 ALTER TABLE `documenti_causdocu` DISABLE KEYS */;
INSERT INTO `documenti_causdocu` VALUES ('CA','Carico di Magazzino','I','CA','CA','CAR'),('CP','Caparra','V','CP','CP','RIS'),('DA','DDT di Acquisto','A','DA','DA','CAR'),('DDTVE','Documento di vendita','V','DV','DDTVE',NULL),('DV','DDT di Vendita','V','FV','DV','SCA'),('FA','Fattura di Acquisto','A','FA','FA','CAR'),('FAI','Fattura di Acquisto Immediata','A','FA','FAI','CAR'),('FC','Fattura di Acconto','V','FV','FC',NULL),('FV','Fattura di Vendita','V','FV','FV',NULL),('FVCO','Fattura di Vendita nei Corrispettivi','V','FV','FVCO','SCA'),('FVI','Fattura di Vendita Immediata','V','FV','FVI','SCA'),('NA','Nota di credito a Fornitore','A','NA','NA','SCA'),('NV','Nota di credito Cliente','V','NV','NV','CAR'),('OA','Ordine di Acquisto','A','OA','OA','ORD'),('OP','Ordine di Produzione','I','OP','OP','ORD'),('OV','Ordine di Vendita','V','OV','OV','IMP'),('PV','Preventivo di vendita','V','PV','PV',NULL),('RC','DDT di Reso merce a fornitore','A','RC','RC','SCA'),('RCQ','Check Ingresso','A','RC','RCQ','CAR'),('RECV','Reso Conto Vendita','V','RV','RECV','SCA'),('RF','Ricevuta Fiscale','V','RF','RF','SCA'),('RFCO','Ricevuta Fiscale nei Corrispettivi','V','RF','RFCO','SCA'),('RS','Merce Scaduta','V','RS','RS','SCA'),('SC','Scarico di Magazzino','I','SC','SC','SCA'),('SP','Spese Genetali','A','SP','SP',NULL),('TR','Trasferimento tra magazzini','I','TR','TR','TRA');
/*!40000 ALTER TABLE `documenti_causdocu` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `documenti_causmaga`
--

LOCK TABLES `documenti_causmaga` WRITE;
/*!40000 ALTER TABLE `documenti_causmaga` DISABLE KEYS */;
INSERT INTO `documenti_causmaga` VALUES ('CAR','Carica Magazzino',1,0,0,0,'CAR',NULL),('IMP','Impegnato da Cliente',0,1,0,0,'IMP',NULL),('ORD','Ordinato a Fornitore',0,0,1,0,'ORD',NULL),('RIS','Riservato a Cliente',0,0,0,1,'RIS',NULL),('SCA','Scarica Magazzino',-1,0,0,0,'SCA',NULL),('TRA','Trasferimento',-1,0,0,1,'TRA','CAR');
/*!40000 ALTER TABLE `documenti_causmaga` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `documenti_codiciva`
--

LOCK TABLES `documenti_codiciva` WRITE;
/*!40000 ALTER TABLE `documenti_codiciva` DISABLE KEYS */;
INSERT INTO `documenti_codiciva` VALUES ('10','Iva 10%',10.00,'10'),('20','Iva 20%',20.00,'20'),('21','Iva 21%',21.00,'21'),('22','Iva 22%',22.00,'22'),('ESA10','Esente Art.10 DPR 633/72',0.00,'ESA10'),('ESC15','Escluso Art. 15',0.00,'ESC15'),('ESTIM','Iva assolta a monte da Tim p.i.00488410010(ex Art.74 II comma 1,DPR 26 Ottobre 1972 n.633)',0.00,'ESTIM'),('ESTRE','Iva assolta a monte da Tre p.i.13378520152(ex Art.74 II comma 1,DPR 26 Ottobre 1972 n.633)',0.00,'ESTRE'),('ESVOD','Iva assolta a monte da Vodafone p.i.08539010010(ex Art.74 II comma 1,DPR 26 Ottobre 1972 n.633)',0.00,'ESVOD'),('ESWIN','Iva assolta a monte da Wind p.i.05410741002(ex Art.74 II comma 1,DPR 26 Ottobre 1972 n.633)',0.00,'ESWIN'),('FCIVA','Fuori campo IVA(art.2 II comma e Art.74 II comma DPR 633/72',0.00,'FCIVA'),('NIA82','Non imponibile Articolo 8, comma 2, lettera c), D.P.R. 633/1972',0.00,'NIA82'),('NIA9','Non imponibile Articolo 9 D.P.R. 633/1972',0.00,'NIA9'),('RCH','Op. soggetta a reverse charge ex art. 17 c 6 lettera a ter, n. DPR 633/72',22.00,'RCH');
/*!40000 ALTER TABLE `documenti_codiciva` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `documenti_doctipba`
--

LOCK TABLES `documenti_doctipba` WRITE;
/*!40000 ALTER TABLE `documenti_doctipba` DISABLE KEYS */;
INSERT INTO `documenti_doctipba` VALUES ('AM','Mancanti Kit','I',100,0,0),('CA','Carico di Magazzino','I',75,0,0),('CP','Caparra','V',60,1,0),('DA','DDT di Acquisto','A',10,0,0),('DP','Dichiarazione di Produzione','I',95,0,0),('DV','DDT di Vendita','V',45,0,0),('FA','Fattura di Acquisto','A',15,1,0),('FV','Fattura di Vendita','V',50,1,0),('GA','Documento Generico Passivo','A',50,0,0),('GV','Documento Generico Attivo','V',130,0,0),('IA','Documenti Interno Attivo','V',120,0,1),('IP','Documenti Interno Passivo','A',40,0,1),('NA','Nota di credito a Fornitore','A',30,1,0),('NV','Nota di credito Cliente','V',55,1,0),('OA','Ordine di Acquisto','A',5,0,0),('OP','Ordine di Produzione','I',90,0,0),('OV','Ordine di Vendita','V',40,0,0),('PA','Richiesta Offerta Fornitore','A',35,0,0),('PV','Preventivo di vendita','V',35,0,0),('RC','DDT di Reso merce a fornitore','A',25,0,0),('RF','Ricevuta Fiscale','V',65,1,0),('RS','Merce Scaduta','V',70,0,0),('RV','Reso da cliente','V',110,0,0),('SC','Scarico di Magazzino','I',80,0,0),('SP','Spese Generali','A',20,0,0),('TR','Trasferimento tra magazzini','I',85,0,0);
/*!40000 ALTER TABLE `documenti_doctipba` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2023-11-11 17:20:48
