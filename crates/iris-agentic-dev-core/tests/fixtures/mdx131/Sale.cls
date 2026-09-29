/// Source rows for the spec 131 MDX fixture cubes. The rows are written by the live test, not here.
Class IadLive131.Sale Extends %Persistent
{

Property Region As %String;

/// 1, 2 or 3. The cube shows these as Retail, Online and Phone.
Property Channel As %Integer;

Property SaleDate As %Date;

/// Doctors 11 and 13 are both named Smith.
Property Doctor As %Integer;

Property DoctorName As %String;

/// Empty on one row, so the measure has an empty cell.
Property Amount As %Numeric;

}
