*Jira Ticket Tool ENG_v1.2*

*How to use*
1.Enter Jira url
Example: https://*companyName*.atlassian.net

2.Enter User (your Jira login email)
Example: *ppl*@*company*.com

3.Enter API token
On your JIRA web page, go to: 
Jira - top right corner - Manage Account - security - create and manage API tokens - create one and paste

(!!:a jira_config file gets generated under same directory as the main program when exiting the program. JIRA URL and User are automatically saved, and check "Save API Token" saves entered API token.)


*Functionalities*
1.Click "Get Latest 10 Tickets" to get latest 10 Tickets of which you are reporter, assignee or watcher.
Click again to get the next 10 latest ones, and so forth.

2.Enter ticket number in "Search Ticket" and click "search" to get tickets you want to look upon. As long as "AAA-####" is intact, spaces and symbols do not matter.

Examples of acceptable entry:
"AAA-1234AAA-1248AAA-1375"
"AAA-1234#$,   AAA-1248(*    AAA-1375wrw"
"AAA-1234
 AAA-1248
 AAA-1375"

3.Left click on items in the ticket list pulls out ticket#, title, description, and conversation.

4.Select (multi-select using ctrl and shift are accepted) from the ticket list and click "Open Selected" opens selected ticket(s) in default browser.

5.Select from ticket list and click "Lock Selected", a "*" will appear next to ticket# and that ticket is pinned to the top and stay even when get 10 new/search/exit program;

Select locked ticket and click "Lock Selected" will unlock selected tickets.

6.Select from ticket list and click "Export Selected", ticket# will get exported into a .txt named with current time, mm/dd/yyyy and number of ticket# exported. Locked tickets keep their marks and will not interfere when doing search with the *