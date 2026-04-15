package main

const RoomPrefix = "SiteA - Room"

func Room(n int) string {
	return RoomPrefix + " " + itoa(n)
}

func itoa(n int) string {
	if n < 0 {
		return "-" + itoa(-n)
	}
	if n < 10 {
		return string(rune('0' + n))
	}
	return itoa(n/10) + string(rune('0'+n%10))
}

// Task constants
const (
	TaskRoom1        = "SiteA - Room 1"
	TaskRoom2        = "SiteA - Room 2"
	TaskRoom3        = "SiteA - Room 3"
	TaskRoom4        = "SiteA - Room 4"
	TaskRoom5        = "SiteA - Room 5"
	TaskRoom6        = "SiteA - Room 6"
	TaskRoom7        = "SiteA - Room 7"
	TaskRoom8        = "SiteA - Room 8"
	TaskRoom9        = "SiteA - Room 9"
	TaskRoom10       = "SiteA - Room 10"
	TaskRoom11       = "SiteA - Room 11"
	TaskRoom12       = "SiteA - Room 12"
	TaskRoom13       = "SiteA - Room 13"
	TaskRoom14       = "SiteA - Room 14"
	TaskRoom15       = "SiteA - Room 15"
	TaskRoom16       = "SiteA - Room 16"
	TaskRoom17       = "SiteA - Room 17"
	TaskRoom18       = "SiteA - Room 18"
	TaskRoom19       = "SiteA - Room 19"
	TaskRoom20       = "SiteA - Room 20"
	TaskLead         = "SiteA - Lead"
	TaskEveShift1    = "SiteA - EveShift1 3p"
	TaskEveShift2    = "SiteA - EveShift2 12p"
	TaskBackup1      = "SiteA - Backup1"
	TaskBackup2      = "SiteA - Backup2"
	TaskSpecialty2Day = "SiteA - Specialty2 Day"
	TaskSiteBRoom    = "SiteB - Room"

	GridRoom        = "SiteA - Room"
	GridRoom8       = "SiteA - Room8"
	GridNoCall      = "No Call"
	GridCoordinator = "SiteA - Coordinator"

	DetectSpecialty1       = "Specialty1"
	DetectSpecialty2OnCall = "Specialty2 OnCall"
	DetectSpecialty2Clinic = "Specialty2 Clinic"
	DetectSpecialty3       = "Specialty3"
	DetectSiteC            = "SiteC"
)

var RoomList1To14 = []string{
	TaskRoom1, TaskRoom2, TaskRoom3, TaskRoom4, TaskRoom5,
	TaskRoom6, TaskRoom7, TaskRoom8, TaskRoom9, TaskRoom10,
	TaskRoom11, TaskRoom12, TaskRoom13, TaskRoom14,
}

var RoomList1To6 = []string{
	TaskRoom1, TaskRoom2, TaskRoom3, TaskRoom4, TaskRoom5, TaskRoom6,
}

var RoomList1To5 = []string{
	TaskRoom1, TaskRoom2, TaskRoom3, TaskRoom4, TaskRoom5,
}

var HighCostTasks = []string{
	TaskRoom1, TaskRoom2, TaskRoom3, TaskEveShift1, TaskEveShift2,
}

var ParttimeExcluded = []string{
	TaskRoom1, TaskRoom2, TaskRoom3, TaskRoom4, TaskRoom5,
	TaskRoom10, TaskRoom11, TaskRoom12,
}
