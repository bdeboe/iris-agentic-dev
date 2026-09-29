/// Spec 131 fixture cube over IadLive131.Sale.
Class IadLive131.SalesCube Extends %DeepSee.CubeDefinition [ DependsOn = IadLive131.Sale ]
{

XData Cube [ XMLNamespace = "http://www.intersystems.com/deepsee" ]
{
<cube xmlns="http://www.intersystems.com/deepsee" name="IadLive131Sales" sourceClass="IadLive131.Sale">
  <dimension name="RegionD" hasAll="true">
    <hierarchy name="H1">
      <level name="Region" sourceProperty="Region"/>
    </hierarchy>
  </dimension>
  <dimension name="ChannelD" hasAll="true">
    <hierarchy name="H1">
      <level name="Channel Name" sourceProperty="Channel" rangeExpression="1:Retail;2:Online;3:Phone;"/>
    </hierarchy>
  </dimension>
  <dimension name="DateD" type="time" sourceProperty="SaleDate" hasAll="true">
    <hierarchy name="Actual">
      <level name="YearSold" timeFunction="Year"/>
      <level name="MonthSold" timeFunction="MonthYear"/>
    </hierarchy>
  </dimension>
  <dimension name="DoctorD" hasAll="true">
    <hierarchy name="H1">
      <level name="Doctor" sourceProperty="Doctor">
        <property name="Name" sourceProperty="DoctorName" isName="true"/>
      </level>
    </hierarchy>
  </dimension>
  <measure name="Amount" sourceProperty="Amount" aggregate="SUM"/>
</cube>
}

}
