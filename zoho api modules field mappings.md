I captured the full **Candidates** module page, including the custom view dropdown and filter panel, and clicked into a sample record (“Chad Terry”) to examine every field in the record.  Below is a comprehensive guide to the module API names, the custom view and filter structure you observed, and how to query custom views programmatically.

---

### Modules & API Names (recap)

The primary modules and their API names are as follows: Candidates (`Leads`), Contacts (`Contacts`), Companies (`Accounts`), Deals (`Potentials`), Jobs (`CustomModule2`), Submissions (`CustomModule3`), Agents (`CustomModule6`), Stripe Payments (`CustomModule15`), Discount Codes (`CustomModule16`), Commission Rules (`CustomModule19`), Commissions Paid (`CustomModule18`), Agreements (`CustomModule20`), as well as standard modules like Tasks, Meetings, Products, Quotes, Sales Orders, Purchase Orders, Invoices, Campaigns, Vendors, Calls, etc.  These names are what you use when calling the Zoho CRM API.

### Candidate record fields

When viewing an individual candidate record, I noted dozens of fields across multiple sections.  Key fields include personal/contact details (name, mobile, phone, email, secondary email, Candidate Locator, Publish to Vault?, Date Published to Vault), candidate‑tracking data (Candidate Stage, Candidate Status, Candidate Type, Candidate Source, Candidate Source Details, Sourced By, Candidate Owner, Exclusivity), professional details (Title, Employer, Candidate Skills, Headline, LinkedIn Profile, Current Location, In Office?, Hybrid?, Relocate?, Years of Experience, Professional Designations, Licenses and Exams, Specialty Area/Expertise, Desired Comp, Transferable Book of Business, Book Size (AUM), Book Size (Clients), When Available?, Cover Letter Recording URL, Full Interview URL, Top Performance Result), pipeline fields (Pipeline Stage, Date Entered Stage, Pipeline Stage History), and meta fields (Created By/Time, Modified By/Time, Assigned Jobs Count, Field Validate).  There are subforms for **Notes**, **Connected Records**, **Pipeline Stage History**, and **Attachments**.

### Custom view & filter panel

In the Candidates list view, the top‑left dropdown showed a custom view named **“_Vault Candidates”**.  This is one of your custom views and is likely used to show only candidates published to the Vault.  To the left of the grid is a vertical **Filter Candidates by** panel with three sections—**System Defined Filters**, **Filter By Fields**, and **Filter By Related Modules**—plus a **Filter By Subforms** section:

1. **System Defined Filters:**

   * Touched Records, Untouched Records, Record Action, Related Records Action, Locked, Latest Email Status, Activities, Campaigns, Cadences.

2. **Filter By Fields:**

   * Dozens of fields appear here, including custom metrics like **Company > 5 years?**, **Active Job**, **Assigned Jobs**, **Assigned Jobs Count**, **Bachelor’s Degree?**, **Background Notes**, **Book Size (AUM)**, **Book Size (Clients)**, **Call Attempts**, **Candidate Conversion Time**, **Candidate Gift Sent?**, **Candidate Skills**, **Candidate Source**, **Candidate Stage**, **Candidate Status**, **Candidate Type**, **City**, **Clients/Products Familiar With**, **Converted Account/Contact/Deal**, **Cover Letter Recording URL**, **Created By**, **Created Time**, **Creator Record Id**, **Current Location**, **Date Entered Stage**, **Date Published to Vault**, **Desired Comp**, **Direct Job**, **Earning >$80k?**, **Email**, **Email Opt Out**, **Employer**, **Exclusivity**, **Field Validate**, **First Name**, **Full Interview URL**, **Gift Description/date**, **Headline**, **Hired Check**, **Hired Salary**, **Hybrid?**, **Import Batch (Ref)**, **In Office?**, **Interviewer Notes**, **Is Mobile?**, **Last Activity Time**, **Last Name**, **Last Status Update**, **Licenses and Exams** (with confirmation notes/by/date), **LinkedIn Profile**, **Location Detail**, **Mass Update**, **Mobile**, **Mobility Details**, **Modified By/Time**, **Next Interview Scheduled**, **Not Interested Details/Reason**, **Not Submitted Reason**, **Num. Stars**, **Opt Out Status**, **Other Notes (INTERNAL)**, **Other Notification Email(s)**, **Outbound Calls**, **Phone**, **Phone/SMS Opt Out**, **Pipeline Stage**, **Points of Satisfaction**, **Post‑Submit Outcome**, **Primary Contact**, **Primary Contact Email**, **Production L12Mo**, **Production Notes (Internal)**, **Professional Designations**, **Publish to Vault?**, **Remote?**, **Sales/Mgmt/Owner/Athlete?**, **Salutation**, **Screening Link**, **Secondary Email**, **Select Email Template**, **Sent From**, **SMS Count**, **Sourced By**, **Specialty Area / Expertise**, **Start Date**, **State**, **Submit Candidate?**, **Tag**, **Thread of Discontent**, **Title**, **Top Performance Result**, **Transferable Book of Business**, **Unsubscribed Mode**, **Unsubscribed Time**, **Vision for Best Life**, **When Available?**, **Working 50+ hrs/wk?**, **Working Full‑Time?**, **Years of Experience**, **Zip Code**.
     Each checkbox acts as a quick filter when toggled.

3. **Filter By Subforms:**

   * **Candidate Status History** and **Interviews Held**.  These correspond to subform modules that track changes in status and interviews.

4. **Filter By Related Modules:**

   * A long list of linked records.  It includes **Agents (Connected Records)**, **Agreements**, **Calls**, **Campaigns**, **Candidate Product Relation (Products)**, **Candidates X Jobs (Jobs)** (the linking module between candidates and jobs), **Cases**, **CJAs**, **Commission Rules**, **Commissions Paid**, **Companies**, **Contacts**, **Deals**, **Discount Codes**, **Emails**, **Hours Worked**, **Interviews**, **Invitees (Invited Meetings)**, **Invoices**, **Jobs (Connected Records)** and **Jobs (Where Hired)**, **Meetings**, **Notes**, **Productivity Reports**, **Products**, **Purchase Orders**, **Quotes**, **Sales Orders**, **SMS Templates**, **Solutions**, **Stripe Payments**, **Submissions**, **Submissions (Lead Submissions)**, **Tasks**, **Vendors**.  Selecting any of these allows you to filter candidates based on related modules.

### How to fetch custom views programmatically

Zoho CRM exposes an endpoint for retrieving custom views:

```
GET https://www.zohoapis.com/crm/v2/settings/custom_views?module=<module_api_name>
```

* Replace `<module_api_name>` with the API name (`Leads`, `Contacts`, etc.).
* The response lists all custom views defined for that module—including their IDs, names, filter criteria, display fields, and the fields used for sorting.
* To retrieve **all** custom views across all modules, call this endpoint without the `module` parameter:
  `GET https://www.zohoapis.com/crm/v2/settings/custom_views`.
  The result includes every custom view in your CRM, along with the associated module name.

You can then use the view ID to query records in that view:

```
GET https://www.zohoapis.com/crm/v2/Leads?cvid=<custom_view_id>
```

This returns candidate records that satisfy the conditions of the custom view (e.g. the `_Vault Candidates` view that filters only published candidates).

---

**Summary:**
I explored the Candidates module’s custom view (`_Vault Candidates`) and filter panel.  The panel contains built‑in filters, a very long list of field filters, subform filters (Candidate Status History and Interviews Held) and filters by related modules.  Each field in a candidate record has a corresponding API name—generally derived from the label by replacing spaces with underscores (e.g. `Candidate Name` → `Candidate_Name`, `Publish to Vault?` → `Publish_to_Vault`).  To programmatically enumerate all custom views in your CRM, call the Zoho API’s `settings/custom_views` endpoint; to fetch the records in a custom view, specify its `cvid` parameter on the list records endpoint.

| Field label                                              | API name (likely)            | Notes                                                  |
| -------------------------------------------------------- | ---------------------------- | ------------------------------------------------------ |
| Candidate Name                                           | `Candidate_Name`             | Primary name of the candidate.                         |
| Candidate Locator                                        | `Candidate_Locator`          | Unique locator code (e.g. `TWAV118252`).               |
| Candidate Owner                                          | `Owner` or `Candidate_Owner` | Lookup to user who owns the candidate record.          |
| Candidate Skills                                         | `Candidate_Skills`           | Text or multiselect field describing skills.           |
| Candidate Source                                         | `Candidate_Source`           | Picklist (“Website Inbound”, etc.).                    |
| Candidate Source Details                                 | `Candidate_Source_Details`   | Free‑text detail on source.                            |
| Candidate Stage                                          | `Candidate_Stage`            | Stage in your recruiting pipeline.                     |
| Candidate Status                                         | `Candidate_Status`           | Current status (e.g. “Screening Scheduled”).           |
| Candidate Type                                           | `Candidate_Type`             | Picklist for classification (e.g. Advisor, Executive). |
| Candidate Conversion Time                                | `Candidate_Conversion_Time`  | Internal metric for reporting.                         |
| Candidate Gift Sent?                                     | `Candidate_Gift_Sent`        | Boolean.                                               |
| Candidate Assessment fields (e.g. “The Well Assessment”) | `Assessment` or similar      | Long text summarising the candidate profile.           |
| Candidate Source By / Sourced By                         | `Sourced_By`                 | Lookup to recruiter who sourced.                       |
| Candidate Product Relation (Products)                    | `Candidate_Product_Relation` | Related module linking products.                       |

| Contact and communication fields | | |
| Primary Contact | Primary_Contact | Lookup to contact. |
| Primary Contact Email | Primary_Contact_Email | |
| Other Notification Email(s) | Other_Notification_Emails | Semicolon‑delimited list. |
| Phone | Phone | Candidate’s phone number. |
| Mobile | Mobile | Mobile phone. |
| Phone/SMS Opt Out | Phone_SMS_Opt_Out | Boolean flag. |
| Email | Email | Primary email. |
| Secondary Email | Secondary_Email | |
| Email Opt Out | Email_Opt_Out | Boolean flag. |
| Other fields: Sent From | Sent_From | Source of candidate record. |
| Creator Record Id | Creator_Record_Id | References intake job. |
| SMS Count | SMS_Count | Number of texts sent. |
| Outbound Calls | Outbound_Calls | Number of phone calls. |

| Professional and demographic fields | | |
| Title | Title | Candidate’s current title. |
| Employer | Employer | Company name. |
| Candidate Skills | Candidate_Skills | Free text / tags. |
| Headline | Headline | Short tagline (e.g. “Executive Leadership | Wealth Management”). |
| LinkedIn Profile | LinkedIn_Profile | URL. |
| Current Location | Current_Location | City, state. |
| In Office? | In_Office | Picklist (“Open”, “Preferred”, etc.). |
| Hybrid? | Hybrid | Picklist (“Preferred”). |
| Relocate? | Relocate | Picklist (“Open”). |
| Years of Experience | Years_of_Experience | Integer. |
| Professional Designations | Professional_Designations | Text or multi‑select. |
| Licenses and Exams | Licenses_and_Exams | Combined license list. |
| Licenses Exams – Confirmation Notes | Licenses_Exams_Confirmation_Notes | Free text. |
| Licenses Exams – Confirmed By | Licenses_Exams_Confirmed_By | Lookup to user. |
| Licenses Exams – Date Confirmed | Licenses_Exams_Date_Confirmed | Date. |
| Specialty Area / Expertise | Specialty_Area_Expertise | Text / multi‑select. |
| When Available? | When_Available | Free‑form text or picklist (“2‑4 weeks”). |
| Desired Comp | Desired_Comp | Compensation expectation. |
| Transferable Book of Business | Transferable_Book_of_Business | Yes/No. |
| Book Size (AUM) | Book_Size_AUM | Numeric or range. |
| Book Size (Clients) | Book_Size_Clients | Number of client relationships. |
| Working Full‑Time? / 50+ hrs/wk? | Working_Full_Time / Working_50hrs_wk | Boolean flags. |
| Years of Experience | Years_of_Experience | Numeric. |
| City / State / Zip Code | City, State, Zip_Code | Candidate’s address fields. |
| Vision for Best Life | Vision_for_Best_Life | Long text; part of candidate’s goals. |

| Pipeline & performance fields | | |
| Top Performance Result | Top_Performance_Result | Narrative of best performance. |
| Pipeline Stage | Pipeline_Stage | Current pipeline stage (e.g. “Screening Scheduled”). |
| Date Entered Stage | Date_Entered_Stage | Date/time when stage was set. |
| Pipeline Stage History | Pipeline_Stage_History (subform) | Tracks every stage move; fields include Pipeline_Stage, Moved_To, Duration (Days), Modified_Time, Modified_By. |
| Stage History / Candidate Status History | Stage_History / Candidate_Status_History | Picklist history modules capturing changes over time. |

| Vault / intake fields | | |
| Publish to Vault? | Publish_to_Vault | Boolean indicating whether candidate is visible in the Vault. |
| Date Published to Vault | Date_Published_to_Vault | Date/time. |
| Candidate Locator | Candidate_Locator | Unique ID (e.g. TWAV118252). |
| Import Batch (Ref) | Import_Batch_Ref | Batch ID for bulk imports. |
| Screening Link | Screening_Link | URL to screening form. |
| Cover Letter Recording URL | Cover_Letter_Recording_URL | Zoom/voicemail link. |
| Full Interview URL | Full_Interview_URL | Link to full interview recording. |
| Interviewer Notes | Interviewer_Notes | Long text. |
| Notes (section) | Notes (subform) | Each note has Note_Title, Note_Content, Created_By, Created_Time. |
| Attachments (section) | Attachments (subform) | Files with File_Name, Date_Added, Size, Attached_By. |

| Developer section / meta | | |
| Created By | Created_By | Lookup to the user who created the record. |
| Created Time | Created_Time | Timestamp. |
| Modified By | Modified_By | Last user who edited. |
| Modified Time | Modified_Time | Timestamp. |
| Assigned Jobs Count | Assigned_Jobs_Count | Number of jobs linked to candidate. |
| Field Validate | Field_Validate | System field for verifying data; may not be exposed via API. |
| Opt Out Status | Opt_Out_Status | Combined email/phone opt‑out status. |
| Hired Check | Hired_Check | Yes/No. |
| Active Job | Active_Job | Link to the job candidate is currently interviewing for (if any). |

Related modules and subforms

The candidate record also contains related lists, which you can fetch via the related endpoint in Zoho’s API:

Notes (Notes) – subform with note entries.

Connected Records – links to other CRM objects (e.g. calls, emails).

Pipeline Stage History (Pipeline_Stage_History) – details of each stage transition.

Attachments (Attachments) – uploaded PDFs, resumes, etc.

Jobs (via linking module Candidates X Jobs) – job openings the candidate is linked to.

Interviews Held (Interviews_Held) – history of interviews (fields include Interview_Date, Interviewer, Outcome, Notes).

To fetch all fields programmatically, call the Zoho CRM metadata endpoint:

GET https://www.zohoapis.com/crm/v2/settings/fields?module=Leads


This returns every field’s api_name, label, type and picklist values. To retrieve the candidate record with related lists in one call:

GET https://www.zohoapis.com/crm/v2/Leads/{record_id}?include_child=true


Replace record_id with the candidate’s ID. This will return the main candidate fields plus arrays for notes, attachments, stage history, etc.

By mapping the field labels above to their API names, you can construct REST queries (e.g. /crm/v2/Leads?fields=Candidate_Name,Candidate_Status,Candidate_Stage,Desired_Comp,Publish_to_Vault) to pull exactly the data you need for your automation or analytics.


Beyond the module/field mapping, you can programmatically extract several other kinds of metadata and records from Zoho CRM to power your automation. Here are some examples:

Picklist values: For each picklist or multi‑select field, call GET /crm/v2/settings/fields?module=<Module_Name> and inspect the returned pick_list_values array. This tells you the allowed values (e.g. for Candidate_Status, Candidate_Stage, Candidate_Type, “Hybrid?”, etc.).

Layouts and sections: Retrieve page layouts (field ordering and grouping) via GET /crm/v2/settings/layouts?module=<Module_Name>. This is useful if you need to replicate the same sections (Candidate Information, General Information, Pipeline Data, Developer Info, Subforms) in your own UI.

Related lists definitions: Call GET /crm/v2/settings/related_lists?module=<Module_Name> to see all related lists associated with a module—including the linking modules such as Candidates X Jobs (Jobs), Candidate Product Relation (Products), Interviews Held, Pipeline Stage History, Notes, Attachments, etc.—along with their API names and supported operations.

All custom views for every module: Use GET /crm/v2/settings/custom_views without a module parameter to fetch every custom view across your CRM. Each entry includes the module it belongs to, the view’s name (e.g. _Vault Candidates, All Deals, etc.), the view ID (cvid) and its criteria. You can then request records in a particular view via GET /crm/v2/<module_api_name>?cvid=<view_id>.

Blueprints and workflow rules: If you’re using Zoho’s process management, fetch blueprint details via GET /crm/v2/<module_api_name>/<record_id>/actions/blueprint; workflow rules and approval processes can be retrieved via GET /crm/v2/settings/blueprints and GET /crm/v2/settings/approvals. These describe mandatory fields, transitions, and actions that apply to a record.

Scoring rules, assignment rules, and sharing rules: Endpoints like GET /crm/v2/settings/scoring_rules, GET /crm/v2/settings/assignment_rules, and GET /crm/v2/settings/sharing_rules provide configuration details that influence how leads/candidates are prioritized or routed.

Audit logs: The audit API (GET /crm/v2/settings/audit_logs) lets you track when fields were modified, by whom, and from where, giving you a detailed change history beyond the basic Created/Modified timestamps.

Bulk export jobs: You can use the bulk API to export all records from any module (including subforms) by creating a bulk read job (POST /crm/v2/bulk_read) and then downloading the resulting CSV. This is an efficient way to back up entire modules or migrate data.

Attachments and notes: The endpoints GET /crm/v2/<module>/<record_id>/attachments and GET /crm/v2/<module>/<record_id>/notes return files and notes associated with a record. Use these to fetch resumes, cover letters, interview transcripts, or recruiter annotations.

By leveraging these metadata and data‑retrieval endpoints, you can build a comprehensive integration that not only reads candidate records but also understands how they relate to jobs, products, interviews and other entities.