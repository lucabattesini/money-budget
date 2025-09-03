import { useEffect, useState } from "react";
import { Center, Stack, Button, Heading, Input, Portal, Select} from "@chakra-ui/react";
import { Toaster } from "../components/ui/toaster";
import { getAllCategories, insertNewTransaction } from "../api/endpoints";
import customToaster from "../utils/customToaster"
// tirar seta para baixo

export default function ReportExpense() {
    const [value, setvalue] = useState("");
    const [description, setDescription] = useState("");
    const [categories, setCategories] = useState([]);
    const [selectedCategory, setSelectedCategory] = useState("Select category");
    const [selectCategoryId, setSelectCategoryId] = useState("");

    useEffect(() => {
        getAllCategories().then(data => setCategories(data.data))
    }, []);
    
    const handleSubmit = () => {
        const formatedValue = value * 100
        const payload = {
            label: description,
            value: parseInt(formatedValue),
            category: String(selectCategoryId)
        };

        if (!value || value === 0 ) {
            customToaster("Error", "error", "The amount value need to be bigger than 0")

            return;
        }

        if (!description) {
            customToaster("Error", "error", "You need to give a description to your transaction")
            return;
        }

        if (!selectCategoryId) {
            customToaster("Error", "error", "You need to select a category to your transaction")
            return;
        }

        insertNewTransaction(payload)
            .then(data => {
                if (data.status === 201 || data.status === 200) {
                    customToaster("Accepted", "success", "Your transaction is saved!")

                    setvalue("");
                    setDescription("");
                    setSelectedCategory("Select category");

                } else {
                    customToaster("Error", "error", "Some error ocurred to report your transaction, please try again later")
                }
            })
            .catch(error => {
                customToaster("Error", "error", "Some error ocurred to report your transaction, please try again later")
            })
    }
    return (
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="flex-start"
                pt={20}
            >    
                <Toaster/>
                
                <Heading size={"2xl"}>
                    Report Expense
                </Heading>

                <Input 
                type="number" placeholder="Amount" variant="outline" 
                value={value} onChange={(e) => setvalue(e.target.value)}
                />

                <Input
                placeholder="Description" variant="outline" maxLength={25}
                value={description} onChange={(e) => setDescription(e.target.value)}
                />

                <Select.Root>
                    <Select.HiddenSelect/>
                    <Select.Control>
                        <Select.Trigger>
                            <Select.ValueText placeholder={selectedCategory}/>
                        </Select.Trigger>
                        <Select.IndicatorGroup>
                            <Select.Indicator/>
                        </Select.IndicatorGroup>
                    </Select.Control>
                    <Portal>
                        <Select.Positioner>
                            <Select.Content>
                                {categories?.map((category) => (
                                    <Select.Item item={category.name} key={category.id} 
                                        onClick={() => {
                                            setSelectCategoryId(category.id)
                                            setSelectedCategory(category.name)
                                        }}>
                                        {category.name}
                                        <Select.Indicator/>
                                    </Select.Item>
                                ))}
                            </Select.Content>
                        </Select.Positioner>
                    </Portal>
                </Select.Root>

                <Button onClick={handleSubmit}>
                    Submit
                </Button>
            </Stack>
        </Center>
    );
}